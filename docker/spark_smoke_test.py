from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .appName("phase21-distributed-smoke-test")
    .getOrCreate()
)

count = spark.range(1000).repartition(4).count()

print(f"PHASE21_SPARK_DISTRIBUTED_COUNT={count}")

spark.stop()
