
```
$ kubectl create ns demo-kafka-ml
namespace/demo-kafka-ml created
```

```
$ kubectl apply -n demo-kafka-ml -f ./kafka-cluster
kafka.kafka.strimzi.io/dale created
kafkatopic.kafka.strimzi.io/sensor-topic created
kafkatopic.kafka.strimzi.io/activity-topic created
```

```
$ kubectl apply -n demo-kafka-ml -f ./kafka-ml/k8s
deployment.apps/kafka-ml created
```

```
$ kubectl apply -n demo-kafka-ml -f ./ios-sensor-data/k8s
deployment.apps/ios-sensor-data-bridge created
service/ios-sensor-data-bridge created
route.route.openshift.io/ios-sensor-data-bridge created
```
