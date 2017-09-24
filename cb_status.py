#!/usr/bin/env - python

import urllib, urllib2, cookielib, pprint, json, time, sys, codecs, base64, random
import settings
from create_dataset import PRODUCTS as PRODUCTS
from txcouchbase.bucket import Bucket

HOST="http://{}:8091".format(settings.NODES[0])
BUCKET_URL = HOST + "/pools/default/buckets"
NODE_URL = HOST + "/pools/default/serverGroups"
INDEX_URL = HOST + "/indexStatus"
SERVICE_URL = HOST + "/pools/default/nodeServices"
FTS_URL = "http://{}:8094/api/index/{}"
XDCR_URL = HOST + "/pools/default/remoteClusters"
USERNAME=settings.ADMIN_USER
PASSWORD=settings.ADMIN_PASS
AUTH_STRING = base64.encodestring('%s:%s' % (USERNAME, PASSWORD)).replace('\n', '')

bucket_name=settings.BUCKET_NAME
user=settings.USERNAME
password=settings.PASSWORD
node=settings.NODES[0]
bucket=Bucket('couchbase://{0}/{1}'.format(node,bucket_name), username=user, password=password)

def getImageForProduct(product):
  for p in PRODUCTS:
    if p['name'] == product[8:]:   #8: is to chop off product:
      return p['image']
  return None


def get_URL(target_url, raise_exception=False):
  while True:
    try:
      req = urllib2.Request(target_url)
      req.add_header("Authorization", "Basic %s" % AUTH_STRING)   
      return urllib2.urlopen(req, timeout=0.1).read()
    except Exception as e:
      if raise_exception:
        raise
      print ("Could not retrieve URL: " + str(target_url) + str(e))
      time.sleep(1)

def getBucketStatus():
  bucket_response = json.loads(get_URL(BUCKET_URL))
  item_count = bucket_response[0]['basicStats']['itemCount']

# Returns a list of nodes and their statuses
def getNodeStatus():
  default_status = { "hostname": "n/a", "ops": 0, "status": "out"}
  node_list = [dict(default_status) for x in range(5)]
  kv_nodes = index = 0
  node_response   = json.loads(get_URL(NODE_URL))
  for node in node_response['groups'][0]['nodes']:
    if "kv" in node['services']:
      index = kv_nodes
      kv_nodes += 1
    elif "n1ql" in node['services']:
      index = 3
    elif "fts" in node['services']:
      index = 4
    node_list[index]['hostname'] = node['hostname']
    # First check for nodes that are fully fledged members of the cluster
    # And if they are KV nodes, check how many ops they're doing
    if node['status'] == "healthy" and node['clusterMembership'] == "active":
      node_list[index]['status'] = "ok"
      if "kv" in node['services'] and 'cmd_get' in node['interestingStats']:
        node_list[index]['ops'] = node['interestingStats']['cmd_get']
    # Check for cluster members that are unhealthy (in risk of being failed)
    # We will highlight these with a red border
    elif node['clusterMembership'] == "active" and \
         node['status'] == "unhealthy":
       node_list[index]['status'] = "trouble"
    # Then, nodes that are either failed over or not rebalanced in
    # These will appear as faded
    elif node['clusterMembership'] == "inactiveFailed" or \
         node['clusterMembership'] == "inactiveAdded":
       node_list[index]['status'] = "dormant"
    # Any other status we'll just hide
    else:
      node_list[index]['status'] = "out"
  return node_list

def fts_node():
  response = json.loads(get_URL(SERVICE_URL))
  for node in response["nodesExt"]:
    if 'fts' in node['services']:
      return node['hostname']
  return None

def fts_enabled():
  node_to_query = fts_node()
  if not node:
    return False

  try:
    response = json.loads(get_URL(FTS_URL.format(node_to_query, 'English'),
                                  raise_exception=True))
  except Exception:
    return False
  else:
    return True

def n1ql_enabled():
  index_response = json.loads(get_URL(INDEX_URL))
  return 'indexes' in index_response and any(index['index'] == u'category' and index['status'] == u'Ready' for index in index_response['indexes'])


def xdcr_enabled():
  xdcr_response = json.loads(get_URL(XDCR_URL))
  return len(xdcr_response) > 0

def main(args):
  while True:
    node_list = getNodeStatus()
    for node in node_list:
      if node['status'] == "broken":
        print "{0} has problems".format(node['hostname'])
      else:
        print "{0} is doing {1} ops".format(node['hostname'], node['ops'] )   
    time.sleep(5.0)


if __name__=='__main__':
  sys.exit(main(sys.argv))