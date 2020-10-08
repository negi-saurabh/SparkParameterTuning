#!/usr/bin/env python

import argparse
import imp
import os
import logging

logger = logging.getLogger("sparkperf")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

from commands import *
from cluster import Cluster
from mesos_cluster import MesosCluster
from testsuites import *
from build import SparkBuildManager


parser = argparse.ArgumentParser(description='Run Spark performance tests. Before running, '
    'edit the supplied configuration file.')

parser.add_argument('--config-file', help='override default location of config file, must be a '
    'python file that ends in .py', default="%s/config/config.py" % PROJ_DIR)

parser.add_argument('--additional-make-distribution-args',
    help='additional arugments to pass to make-distribution.sh when building Spark', default="")

args = parser.parse_args()
assert args.config_file.endswith(".py"), "config filename must end with .py"

# Check if the config file exists.
assert os.path.isfile(args.config_file), ("Please create a config file called %s (you probably "
    "just want to copy and then modify %s/config/config.py.template)" %
    (args.config_file, PROJ_DIR))

print "Detected project directory: %s" % PROJ_DIR
# Import the configuration settings from the config file.
print "Loading configuration from %s" % args.config_file
with open(args.config_file) as cf:
    config = imp.load_source("config", "", cf)

# Spark will always be built, assuming that any possible test run
# of this program is going to depend on Spark.
run_pivalue_tests = config.RUN_PI_VALUE_TESTS and (len(config.PIVALUE_TEST) > 0)
run_spark_tests = config.RUN_SPARK_TESTS and (len(config.SPARK_TESTS) > 0)
run_pyspark_tests = config.RUN_PYSPARK_TESTS and (len(config.PYSPARK_TESTS) > 0)
run_tests = run_spark_tests or run_pyspark_tests or run_pivalue_tests


# Only build the perf test sources that will be used.
should_prep_spark = not config.USE_CLUSTER_SPARK and config.PREP_SPARK
should_prep_spark_tests = run_spark_tests and config.PREP_SPARK_TESTS


# Restart Master and Workers
should_restart_cluster = config.RESTART_SPARK_CLUSTER
# Copy all the files in SPARK_HOME 
should_rsync_spark_home = config.RSYNC_SPARK_HOME

# Check that commit ID's are specified in config_file.
if should_prep_spark:
    assert config.SPARK_COMMIT_ID is not "", \
        ("Please specify SPARK_COMMIT_ID in %s" % args.config_file)

# If a cluster is already running from the Spark EC2 scripts, try shutting it down.
if os.path.exists(config.SPARK_HOME_DIR) and should_restart_cluster :
    Cluster(spark_home=config.SPARK_HOME_DIR).stop()

spark_build_manager = SparkBuildManager("%s/spark-build-cache" % PROJ_DIR, config.SPARK_GIT_REPO)


if config.USE_CLUSTER_SPARK:
    cluster = Cluster(spark_home=config.SPARK_HOME_DIR, spark_conf_dir=config.SPARK_CONF_DIR)
else:
    cluster = spark_build_manager.get_cluster(
        commit_id=config.SPARK_COMMIT_ID,
        conf_dir=config.SPARK_CONF_DIR,
        merge_commit_into_master=config.SPARK_MERGE_COMMIT_INTO_MASTER,
        is_yarn_mode=config.IS_YARN_MODE,
        additional_make_distribution_args=args.additional_make_distribution_args)

# rsync Spark to all nodes in case there is a change in Worker config
if should_restart_cluster and should_rsync_spark_home:
    cluster.sync_spark()

# If a cluster is already running from an earlier test, try shutting it down.
if os.path.exists(cluster.spark_home) and should_restart_cluster:
    cluster.stop()

if should_restart_cluster:
    # Ensure all shutdowns have completed (no executors are running).
    cluster.ensure_spark_stopped_on_slaves()

# Build the tests for each project.
spark_work_dir = "%s/work" % cluster.spark_home
if os.path.exists(spark_work_dir):
    # Clear the 'perf-tests/spark/work' directory beforehand, since that may contain scheduler logs
    # from previous jobs. The directory could also contain a spark-perf-tests-assembly.jar that may
    # interfere with subsequent 'sbt assembly' for Spark perf.
    clear_dir(spark_work_dir, ["localhost"], config.PROMPT_FOR_DELETES)

print("Building perf tests...")
if should_prep_spark_tests:
    SparkTests.build()
elif run_spark_tests:
    assert SparkTests.is_built(), ("You tried to skip packaging the Spark perf " +
        "tests, but %s was not already present") % SparkTests.test_jar_path



# Start our Spark cluster.
if should_restart_cluster:
    cluster.start()

if run_pivalue_tests:
    PiValueTest.run_tests(cluster, config, config.PIVALUE_TEST, "piValue-Tests",
                             config.SPARK_OUTPUT_FILENAME)

if run_spark_tests:
    SparkTests.run_tests(cluster, config, config.SPARK_TESTS, "Spark-Tests",
                         config.SPARK_OUTPUT_FILENAME)

if run_pyspark_tests:
    PythonTests.run_tests(cluster, config, config.PYSPARK_TESTS, "PySpark-Tests",
                          config.PYSPARK_OUTPUT_FILENAME)


if should_restart_cluster:
    cluster.stop()

print("Finished running all tests.")
