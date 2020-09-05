const fs = require('fs');
const app = require('express')();
const http = require('http').Server(app);
const io = require('socket.io')(http);

// types of activities we want to train the system to recognize based
//  on phone sensor data
const VALID_ACTIVITIES = [
    // phone is on the table
    //  it could be face up or face down, but the point is that it's
    //  not being held, touched or used
    'idle',
    // phone is in a pocket, while you are sitting down
    'pocketsitting',
    // phone is in a pocket, while you are standing or walking around
    'pocketmoving',
    // phone is in your hand and is in use
    //  it could be that you're just looking at it, or you're actively
    //  tapping on it
    'inhand',
    // phone is in your hand, and you're running!
    'running',
];

const ACTIVITY = process.argv.slice(-1)[0];
if (!VALID_ACTIVITIES.includes(ACTIVITY)) {
    console.log('Please specify which activity you are collecting training data for');
    console.log(VALID_ACTIVITIES);
    console.log('Usage: node train.js <ACTIVITY>');
    process.exit(-1);
}

console.log('========================');
console.log('TRAINING DATA COLLECTION');
console.log('========================');

// init to a negative number to let us swallow the
//  first samples as this gives stuff time to
//  settle down
let samplesCaptured = -50;

// Sensor data from the phone comes as accelerometer and gyro
//  data separately - but we want to collate them and send them
//  as combined readings
// This is where we store the latest sensor reading of each type.
var lastUpdates = {
    accel : null,
    gyro : null,
};

// HTTP capturing
app.get('/accel', function (req, res) {
    logData('accel', JSON.parse(req.headers.accel));
    res.send('Received accel data.');
});
app.get('/gyro', function (req, res) {
    logData('gyro', JSON.parse(req.headers.gyro));
    res.send('Received gyro data.');
});
app.get('/magnet', function (req, res) {
    res.send('Received magnet data.');
});

// socket.io capturing
io.on('connection', function (socket) {
    console.log('a phone connected');
    socket.broadcast.emit('connection');

    socket.on('disconnect', function () {
        console.log('\nphone disconnected');
        shutdown();
    });
    socket.on('accel', function (data) {
        logData('accel', data);
    });
    socket.on('gyro', function (data) {
        logData('gyro', data);
    });
    socket.on('magnet', function () { });
});

// open the training file where sensor readings will be written
var trainingDataFile = fs.createWriteStream('trainingdata/train-' + ACTIVITY + '.csv', {flags:'a'});

// start the server
var serverrunning = true;
const server = http.listen(3000, function () {
    console.log('listening on *:3000');
    console.log('The first 50 sensor readings will be ignored to give you time ' +
                'to get the phone in the right position');
});

// function for shutting down once we've collected enough training examples
function shutdown() {
    serverrunning = false;
    server.close();
    trainingDataFile.close();

    // say bye-bye!
    console.log('\nTraining data capture complete');
    console.log(samplesCaptured + ' samples of ' + ACTIVITY +
                ' have been added to the training data file');
    process.exit(0);
}

// function for recording a single sensor reading
function logData(dataType, data) {
    if (serverrunning) {
        lastUpdates[dataType] = data;

        if (samplesCaptured === 0) {
            console.log('\nStarting to record training samples of ' + ACTIVITY);
            console.log('This will collect sensor readings for 60 seconds');
            setTimeout(shutdown, 60000);
        }

        if (samplesCaptured >= 0) {
            trainingDataFile.write([
                lastUpdates.accel[0],
                lastUpdates.accel[1],
                lastUpdates.accel[2],
                lastUpdates.gyro[0],
                lastUpdates.gyro[1],
                lastUpdates.gyro[2],
            ].join(',') + '\n');
        }

        process.stdout.write('.');
        samplesCaptured += 1;
    }
}
