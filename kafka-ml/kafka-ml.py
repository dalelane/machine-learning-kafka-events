# used to get environment variables with config info
import os

# used to read the training data CSV files
import pandas as pd
# used for shaping data
import numpy as np

# used to map our activity categories to values
from sklearn.preprocessing import OneHotEncoder

# used to make an ML model
from tensorflow import keras
from tensorflow.keras import Sequential
from tensorflow.keras.layers import Bidirectional, LSTM, Dropout, Dense

# used to read data from a Kafka topic for inferencing
from tensorflow_io.kafka import KafkaDataset
from tensorflow.io import decode_csv

# used to send the inference events to an output topic
from kafka import KafkaProducer

# ---------------------------------------------------------------------------

# get the environment variables that identify the
#  Kafka topics being used
KAFKA_BOOTSTRAP=os.environ.get("KAFKA_BOOTSTRAP")
RAW_EVENTS_TOPIC=os.environ.get("RAW_EVENTS_TOPIC")
PROCESSED_EVENTS_TOPIC=os.environ.get("PROCESSED_EVENTS_TOPIC")
print("Using Kafka cluster at %s" % (KAFKA_BOOTSTRAP))
print("Reading sensor events from %s and producing predictions to %s" % (RAW_EVENTS_TOPIC, PROCESSED_EVENTS_TOPIC))

# ---------------------------------------------------------------------------

# These are the types of activity that we will
#  learn to recognize
labels = [
    # phone is on the table
    #  it could be face up or face down, but the point
    #  is that it's not being held, touched or used
    "idle",
    # phone is in your hand and is in use
    #  it could be that you're just looking at it, or
    #  you're actively tapping on it
    "inhand",
    # phone is in a pocket, while you are standing or
    #  walking around
    "pocketmoving",
    # phone is in a pocket, while you are sitting down
    "pocketsitting",
    # phone is in your hand, and you're running!
    "running"
]

# columns in the CSV files used in this project
columns = [
    # accelerometer data
    "accel_x",
    "accel_y",
    "accel_z",
    # gyroscope data
    "gyro_x",
    "gyro_y",
    "gyro_z"
]

# ---------------------------------------------------------------------------

# time-series models created using sliding overlapping window

# size of each window - the number of samples in each value
WINDOW_SIZE=40
# how often to start a new window
WINDOW_STEP=15

# in other words,
#  the first window contains samples 0-40
#  the second window contains samples 15-55
#  the third window contains samples 30-70
#  the fourth window contains samples 45-85
#  the fifth window contains samples 60-100
#  the sixth window contains samples 75-115
#  etc.

# This lets us get lots of training example sequences out of
# a small-ish number of sensor samples

# Adds values to the provided arrays using a training file
#
# This function is a clunky way of creating the windows as
#  described above.
#
#  label - one of 'labels' - the type of activity that the samples describe
#  input_windows - array of windows being created to contain input data
#  target_windows - array of target values for each input_window
#
#  returns updated input_windows, target_windows
def add_to_training(label, input_windows, target_windows):
    # read training data CSV
    filename = "trainingdata/train-" + label + ".csv"
    df = pd.read_csv(filename, header=None, names=columns)
    inputs = df[columns]
    num_samples = len(inputs)

    for start_idx in range(0, num_samples - WINDOW_SIZE, WINDOW_STEP):
        end_idx = start_idx + WINDOW_SIZE
        input_windows.append(inputs.iloc[start_idx : end_idx].values)
        target_windows.append(label)

    return input_windows, target_windows

# ---------------------------------------------------------------------------

print("--------------------------------------------------------------")
print(" Preparing training data...")
print("--------------------------------------------------------------")

training_x, training_y = [], []
for label in labels:
    print("Getting training examples for " + label)
    training_x, training_y = add_to_training(label, training_x, training_y)

print("Shaping training data...")
training_x = np.array(training_x)
training_y = np.array(training_y).reshape(-1, 1)

# training shape is the number of samples in a window, by the number of values in a sample
input_shape=(WINDOW_SIZE, len(columns))

# ---------------------------------------------------------------------------

print("--------------------------------------------------------------")
print(" Preparing categories for labels...")
print("--------------------------------------------------------------")

enc = OneHotEncoder(sparse=False).fit(training_y)
training_y = enc.transform(training_y)

# ---------------------------------------------------------------------------

print("--------------------------------------------------------------")
print(" Creating ML model...")
print("--------------------------------------------------------------")

units=64

model = Sequential([
    Bidirectional(LSTM(units, input_shape=input_shape)),

    # protect against overfitting with the relatively small
    #  training data by adding dropout
    Dropout(rate=0.5),

    # generic layer
    Dense(units, activation="relu"),

    # output layer - using the number of possible
    #  activities as the number of units
    Dense(len(labels), activation="softmax")
])

model.compile(loss="categorical_crossentropy",
              metrics=["accuracy"],
              optimizer="adam")

print("Training ML model...")
model.fit(
    training_x, training_y,
    epochs=25,
    # keep the stream of events in sequence
    shuffle=False,
    # don't fill the log with progress bars
    verbose=2
)

# ---------------------------------------------------------------------------

print("--------------------------------------------------------------")
print(" Quick sniff test to verify the ML model...")
print("--------------------------------------------------------------")

# evaluates the model using a test file that contains
# enough samples for a single sliding window
def run_test(test_label):
    filename = "testdata/test-" + test_label + ".csv"

    df = pd.read_csv(filename, header=None, names=columns)
    inputs = df[columns]

    x_test = np.array([ inputs.iloc[0 : WINDOW_SIZE].values ])

    prediction=model.predict(x_test)
    print ("expected   : " + test_label)
    print ("prediction : " + enc.inverse_transform(prediction)[0][0])

run_test("idle")
run_test("inhand")
run_test("pocketsitting")

# ---------------------------------------------------------------------------

print("--------------------------------------------------------------")
print("Preparing Kafka producer...")
print("--------------------------------------------------------------")
producer = KafkaProducer(bootstrap_servers=[KAFKA_BOOTSTRAP],
                         api_version=(2,5,0),
                         client_id="ml-events-producer")

# ---------------------------------------------------------------------------

print("--------------------------------------------------------------")
print("Connecting to Kafka for a stream of events to categorize...")
print("--------------------------------------------------------------")

# take a single sensor reading (as a CSV string) and return it as
#  an array of floats
#
# value - Kafka message payload (for 1 message)
# key - Kafka message key (for 1 message)
#
# returns (value, key) where the value has been decoded
def decode_kafka_message(value, key):
    return (decode_csv(value, [[0.0] for i in range(len(columns))]), key)

# take a batch of sensor readings, and use the model to return
#  the label that it is recognized as
#
# decoded_sensor_data_batch - list (where the size is WINDOW_SIZE)
#                              of decoded messages
#
# returns string with the recognized label for the data
def get_model_inference(decoded_sensor_data_batch):
    predictions = model.predict(np.array([ decoded_sensor_data_batch ]))
    label = enc.inverse_transform(predictions)[0][0]
    return label

test_stream = KafkaDataset(topics=[RAW_EVENTS_TOPIC],
                           servers=KAFKA_BOOTSTRAP,
                           group="tensorflow-kafka",
                           # run forever, even if we stop
                           #  getting events for a while
                           eof=False,
                           # fetch message keys because they
                           #  contain timestamps
                           message_key=True,
                           config_global=[
                               "api.version.request=true"
                           ],
                           # classify new events only, ignore
                           #  historical events
                           config_topic=["auto.offset.reset=latest"])

# translate each of the string messages to an array of 6 numbers
test_stream = test_stream.map(decode_kafka_message)

# read messages into the ML model a batch at a time, using the
# same window size the ML model was trained with
test_stream = test_stream.batch(WINDOW_SIZE, drop_remainder=True)

print("Sending predictions from sensor events")
lastprediction = None

for decoded_batch, keys in test_stream:
    # get prediction
    label = get_model_inference(decoded_batch)

    # if the prediction is different to the last event, send
    #  a message to the predictions topic
    if label != lastprediction:
        lastprediction = label
        producer.send(PROCESSED_EVENTS_TOPIC, label.encode())
