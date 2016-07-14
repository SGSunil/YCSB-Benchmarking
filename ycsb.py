#!/usr/bin/env python
#
# Copyright (c) 2012 - 2015 YCSB contributors. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you
# may not use this file except in compliance with the License. You
# may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License. See accompanying
# LICENSE file.
#

import errno
import fnmatch
import io
import os
import shlex
import sys
import subprocess
try:
    import argparse
except ImportError:
    print >> sys.stderr, '[ERROR] argparse not found. Try installing it via "pip".'
    raise

BASE_URL = "https://github.com/brianfrankcooper/YCSB/tree/master/"
COMMANDS = {
    "shell" : {
        "command"     : "",
        "description" : "Interactive mode",
        "main"        : "com.yahoo.ycsb.CommandLine",
    },
    "load" : {
        "command"     : "-load",
        "description" : "Execute the load phase",
        "main"        : "com.yahoo.ycsb.Client",
    },
    "run" : {
        "command"     : "-t",
        "description" : "Execute the transaction phase",
        "main"        : "com.yahoo.ycsb.Client",
    },
}

DATABASES = {
    "accumulo"     : "com.yahoo.ycsb.db.accumulo.AccumuloClient",
    "aerospike"    : "com.yahoo.ycsb.db.AerospikeClient",
    "basic"        : "com.yahoo.ycsb.BasicDB",
    "cassandra-7"  : "com.yahoo.ycsb.db.CassandraClient7",
    "cassandra-8"  : "com.yahoo.ycsb.db.CassandraClient8",
    "cassandra-10" : "com.yahoo.ycsb.db.CassandraClient10",
    "cassandra-cql": "com.yahoo.ycsb.db.CassandraCQLClient",
    "cassandra2-cql": "com.yahoo.ycsb.db.CassandraCQLClient",
    "cassandra3-cql": "com.yahoo.ycsb.db.CassandraCQLClient3",	
    "couchbase"    : "com.yahoo.ycsb.db.CouchbaseClient",
    "dynamodb"     : "com.yahoo.ycsb.db.DynamoDBClient",
    "elasticsearch": "com.yahoo.ycsb.db.ElasticsearchClient",
    "geode"        : "com.yahoo.ycsb.db.GeodeClient",
    "googledatastore" : "com.yahoo.ycsb.db.GoogleDatastoreClient",
    "hbase094"     : "com.yahoo.ycsb.db.HBaseClient",
    "hbase098"     : "com.yahoo.ycsb.db.HBaseClient",
    "hbase10"      : "com.yahoo.ycsb.db.HBaseClient10",
    "hypertable"   : "com.yahoo.ycsb.db.HypertableClient",
    "infinispan-cs": "com.yahoo.ycsb.db.InfinispanRemoteClient",
    "infinispan"   : "com.yahoo.ycsb.db.InfinispanClient",
    "jdbc"         : "com.yahoo.ycsb.db.JdbcDBClient",
    "kudu"         : "com.yahoo.ycsb.db.KuduYCSBClient",
    "mapkeeper"    : "com.yahoo.ycsb.db.MapKeeperClient",
    "memcached"    : "com.yahoo.ycsb.db.MemcachedClient",
    "mongodb"      : "com.yahoo.ycsb.db.MongoDbClient",
    "mongodb-async": "com.yahoo.ycsb.db.AsyncMongoDbClient",
    "mongodb3"      : "com.yahoo.ycsb.db3.MongoDbClient",
    "mongodb-async3": "com.yahoo.ycsb.db3.AsyncMongoDbClient",	
    "nosqldb"      : "com.yahoo.ycsb.db.NoSqlDbClient",
    "orientdb"     : "com.yahoo.ycsb.db.OrientDBClient",
    "redis"        : "com.yahoo.ycsb.db.RedisClient",
    "s3"           : "com.yahoo.ycsb.db.S3Client",
    "solr"         : "com.yahoo.ycsb.db.SolrClient",
    "tarantool"    : "com.yahoo.ycsb.db.TarantoolClient",
    "voldemort"    : "com.yahoo.ycsb.db.VoldemortClient"
}

OPTIONS = {
    "-P file"        : "Specify workload file",
    "-p key=value"   : "Override workload property",
    "-s"             : "Print status to stderr",
    "-target n"      : "Target ops/sec (default: unthrottled)",
    "-threads n"     : "Number of client threads (default: 1)",
    "-cp path"       : "Additional Java classpath entries",
    "-jvm-args args" : "Additional arguments to the JVM",
}

def usage():
    output = io.BytesIO()
    print >> output, "%s command database [options]" % sys.argv[0]

    print >> output, "\nCommands:"
    for command in sorted(COMMANDS.keys()):
        print >> output, "    %s %s" % (command.ljust(14),
                                        COMMANDS[command]["description"])

    print >> output, "\nDatabases:"
    for db in sorted(DATABASES.keys()):
        print >> output, "    %s %s" % (db.ljust(14), BASE_URL +
                                        db.split("-")[0])

    print >> output, "\nOptions:"
    for option in sorted(OPTIONS.keys()):
        print >> output, "    %s %s" % (option.ljust(14), OPTIONS[option])

    print >> output, """\nWorkload Files:
    There are various predefined workloads under workloads/ directory.
    See https://github.com/brianfrankcooper/YCSB/wiki/Core-Properties
    for the list of workload properties."""

    return output.getvalue()

def check_output(cmd):
    print "******", os.environ
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=os.environ, shell=True)
    stdout, _ = p.communicate()
    if p.returncode:
        raise subprocess.CalledProcessError(p.returncode, cmd)
    return stdout

def debug(message):
    print >> sys.stderr, "[DEBUG] ", message

def warn(message):
    print >> sys.stderr, "[WARN] ", message

def error(message):
    print >> sys.stderr, "[ERROR] ", message

def find_jars(dir, glob='*.jar'):
    jars = []
    for (dirpath, dirnames, filenames) in os.walk(dir):
        for filename in fnmatch.filter(filenames, glob):
            jars.append(os.path.join(dirpath, filename))
    return jars

def get_ycsb_home():
    dir = os.path.abspath(os.path.dirname(sys.argv[0]))
    while "LICENSE.txt" not in os.listdir(dir):
        dir = os.path.join(dir, os.path.pardir)
    return os.path.abspath(dir)

def is_distribution():
    # If there's a top level pom, we're a source checkout. otherwise a dist artifact
    return "pom.xml" not in os.listdir(get_ycsb_home())

# Run the maven dependency plugin to get the local jar paths.
# presumes maven can run, so should only be run on source checkouts
# will invoke the 'package' goal for the given binding in order to resolve intra-project deps
# presumes maven properly handles system-specific path separators
# Given module is full module name eg. 'core' or 'couchbase-binding'
def get_classpath_from_maven(module):
    try:
        debug("Running 'mvn -pl com.yahoo.ycsb:" + module + " -am package -DskipTests "
              "dependency:build-classpath -DincludeScope=compile -Dmdep.outputFilterFile=true'")
        #print "******************"
        #print os.environ['PATH']
        mvn_output = check_output(["mvn", "-pl", "com.yahoo.ycsb:" + module, "-am", "package", "-DskipTests=true", "dependency:build-classpath", "-DincludeScope=compile", "-Dmdep.outputFilterFile=true"])
        print mvn_output
        # the above outputs a "classpath=/path/tojar:/path/to/other/jar" for each module
        # the last module will be the datastore binding
        line = [x for x in mvn_output.splitlines() if x.startswith("classpath=")][-1:]
        return line[0][len("classpath="):]
    except subprocess.CalledProcessError, err:
        error("Attempting to generate a classpath from Maven failed "
              "with return code '" + str(err.returncode) + "'. The output from "
              "Maven follows, try running "
              "'mvn -DskipTests package dependency:build=classpath' on your "
              "own and correct errors." + os.linesep + os.linesep + "mvn output:" + os.linesep
              + err.output)
        sys.exit(err.returncode)

def main():
    p = argparse.ArgumentParser(
            usage=usage(),
            formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('-cp', dest='classpath', help="""Additional classpath
                   entries, e.g.  '-cp /tmp/hbase-1.0.1.1/conf'. Will be
                   prepended to the YCSB classpath.""")
    p.add_argument("-jvm-args", default=[], type=shlex.split,
                   help="""Additional arguments to pass to 'java', e.g.
                   '-Xmx4g'""")
    p.add_argument("command", choices=sorted(COMMANDS),
                   help="""Command to run.""")
    p.add_argument("database", choices=sorted(DATABASES),
                   help="""Database to test.""")
    args, remaining = p.parse_known_args()
    ycsb_home = get_ycsb_home()
    print "ycsb home", ycsb_home

    # Use JAVA_HOME to find java binary if set, otherwise just use PATH.
    java = "java"
    java_home = os.getenv("JAVA_HOME")
    if java_home:
        java = os.path.join(java_home, "bin", "java")
    db_classname = DATABASES[args.database]
    command = COMMANDS[args.command]["command"]
    main_classname = COMMANDS[args.command]["main"]

    # Classpath set up
    binding = args.database.split("-")[0]

    # Deprecation message for the entire cassandra-binding
    if binding == "cassandra":
        warn("The 'cassandra-7', 'cassandra-8', 'cassandra-10', and "
             "cassandra-cql' clients are deprecated. If you are using "
             "Cassandra 2.X try using the 'cassandra2-cql' client instead.")

    if is_distribution():
        db_dir = os.path.join(ycsb_home, binding + "-binding")
        # include top-level conf for when we're a binding-specific artifact.
        # If we add top-level conf to the general artifact, starting here
        # will allow binding-specific conf to override (because it's prepended)
        cp = [os.path.join(ycsb_home, "conf")]
        cp.extend(find_jars(os.path.join(ycsb_home, "lib")))
        cp.extend(find_jars(os.path.join(db_dir, "lib")))
    else:
        warn("Running against a source checkout. In order to get our runtime "
             "dependencies we'll have to invoke Maven. Depending on the state "
             "of your system, this may take ~30-45 seconds")
        db_location = "core" if binding == "basic" else binding
        project = "core" if binding == "basic" else binding + "-binding"
        db_dir = os.path.join(ycsb_home, db_location)
        # goes first so we can rely on side-effect of package
        maven_says = get_classpath_from_maven(project)
        # TODO when we have a version property, skip the glob
        cp = find_jars(os.path.join(db_dir, "target"),
                       project + "*.jar")
        # alredy in jar:jar:jar form
        cp.append(maven_says)
    cp.insert(0, os.path.join(db_dir, "conf"))
    classpath = os.pathsep.join(cp)
    if args.classpath:
        classpath = os.pathsep.join([args.classpath, classpath])

    ycsb_command = ([java] + args.jvm_args +
                    ["-cp", classpath,
                     main_classname, "-db", db_classname] + remaining)
    if command:
        ycsb_command.append(command)
    print >> sys.stderr, " ".join(ycsb_command)
    try:
        return subprocess.call(ycsb_command)
    except OSError as e:
        if e.errno == errno.ENOENT:
            error('Command failed. Is java installed and on your PATH?')
            return 1
        else:
            raise

if __name__ == '__main__':
    sys.exit(main())
