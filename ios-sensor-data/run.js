const app = require('express')();
const http = require('http').Server(app);
const io = require('socket.io')(http);
const { Kafka } = require('kafkajs');

console.log('==========================');
console.log('SUBMITTING SENSOR READINGS');
console.log('==========================');

// get the environment variables that identify the
//  Kafka topics being used
KAFKA_BOOTSTRAP = process.env.KAFKA_BOOTSTRAP;
RAW_EVENTS_TOPIC = process.env.RAW_EVENTS_TOPIC;
console.log('Using Kafka cluster at ' + KAFKA_BOOTSTRAP);
console.log('Producing sensor events to ' + RAW_EVENTS_TOPIC);

// Sensor data from the phone comes as accelerometer and gyro
//  data separately - but we want to collate them and send them
//  as combined readings
// This is where we store the latest sensor reading of each type.
var lastUpdates = {
    accel : null,
    gyro : null,
};

// Ignore the first 15 sensor readings from the phone before we
//  start sending them to Kafka.
var warmup = -15;

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
    });
    socket.on('accel', function (data) {
        logData('accel', data);
    });
    socket.on('gyro', function (data) {
        logData('gyro', data);
    });
    socket.on('magnet', function () { });
});

// prepare Kafka client to use to send raw sensor
//  readings to a topic
const producer = new Kafka({
    clientId: 'iphone',
    brokers: [ KAFKA_BOOTSTRAP ],
}).producer();
producer.connect();

// start the server
http.listen(3000, function () {
    console.log('listening on *:3000');
});

// receiving a sensor reading for sending to Kafka
function logData(dataType, data) {
    lastUpdates[dataType] = data;

    if (warmup > 0) {
        producer.send({
            topic: RAW_EVENTS_TOPIC,
            messages : [ {
                key : new Date().toString(),
                value : [
                    lastUpdates.accel[0],
                    lastUpdates.accel[1],
                    lastUpdates.accel[2],
                    lastUpdates.gyro[0],
                    lastUpdates.gyro[1],
                    lastUpdates.gyro[2],
                ].join(',') } ],
            acks: 0,
        });
    }
    else {
        process.stdout.write('.');
        warmup += 1;
    }
}
