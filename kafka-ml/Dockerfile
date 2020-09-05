FROM tensorflow/tensorflow:2.3.0

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir trainingdata
COPY trainingdata/* ./trainingdata/
RUN mkdir testdata
COPY testdata/* ./testdata/

COPY kafka-ml.py .

CMD [ "python", "./kafka-ml.py" ]
