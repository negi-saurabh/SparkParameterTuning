
import random

import time
import random
import json
import sys
import pyspark



class PerfTest(object):
    def __init__(self, sc):
        self.sc = sc

    def initialize(self, options):
        self.options = options

    def createInputData(self):
        pass

    def runTest(self):
        raise NotImplementedError

    def run(self):
        options = self.options
        rs = []
        for i in range(options.num_trials):
            start = time.time()
            self.runTest()
            rs.append(time.time() - start)
            time.sleep(options.inter_trial_wait)
        return rs

def inside(p):
        x, y = random.random(), random.random()
        return x * x + y * y < 1

class Valueofpi(PerfTest):
    def runTest(self):
        NUM_SAMPLES = self.options.num_tasks
        print(NUM_SAMPLES)
        count = self.sc.parallelize(range(0, NUM_SAMPLES)).filter(inside).count()
        print("haha hehe ho ho Pi is roughly %f" % (4.0 * count / NUM_SAMPLES))



all_tests = [
    "Valueofpi",
]
if __name__ == "__main__":
    import optparse
    parser = optparse.OptionParser(usage="Usage: %prog [options] test_names")
    parser.add_option("--num-trials", type="int", default=1)
    parser.add_option("--num-tasks", type="int", default=1)
    parser.add_option("--inter-trial-wait", type="int", default=0)
    parser.add_option("--list", "-l", action="store_true", help="list all tests")
    parser.add_option("--all", "-a", action="store_true", help="run all tests")
    print("yes1")
    options, cases = parser.parse_args()

    if options.list:
        for n in all_tests:
            print n
        sys.exit(0)

    if options.all:
        cases = all_tests

    sc = pyspark.SparkContext(appName="Pi Value Runner")
    for name in cases:
        print 'run test:', name
        test = globals()[name](sc)
        test.initialize(options)
        test.createInputData()
        results = test.run()
        print "results:", ",".join("%.3f" % t for t in results)

        # JSON results
        javaSystemProperties = sc._jvm.System.getProperties()
        systemProperties = {}
        for k in javaSystemProperties.keys():
            systemProperties[k] = str(javaSystemProperties[k])
        sparkConfInfo = {}  # convert to dict to match Scala JSON
        for (a, b) in sc._conf.getAll():
            sparkConfInfo[a] = b
        jsonResults = json.dumps({"testName": name,
                                  "options": vars(options),
                                  "sparkConf": sparkConfInfo,
                                  "sparkVersion": sc.version,
                                  "systemProperties": systemProperties,
                                  "results": results,
                                  "bestResult:": min(results)},
                                 separators=(',', ':'))  # use separators for compact encoding
        print "jsonResults: " + jsonResults