#!/usr/bin/env python

import argparse
import decimal
import json
import math
import string
import sys
import time
import urllib2
import webbrowser


# Put your API key here!
API_KEY = ''

# Constants - DO NOT CHANGE!
LAT_DISTANCE = 111000 # meters
LNG_DISTANCE = 111000 # meters

# Google location takeout fields
LOCATIONS = 'locations'
TIMESTAMPMS = 'timestampMs'
LATITUDEE7 = 'latitudeE7'
LONGITUDEE7 = 'longitudeE7'
ACCURACY = 'accuracy'
ACTIVITYS = 'activitys'

# Google Places API fields
RESULTS = 'results'
ADDRESS_COMPONENTS = 'address_components'
FORMATTED_ADDRESS = 'formatted_address'
GEOMETRY = 'geometry'
LOCATION = 'location'
LAT = 'lat'
LNG = 'lng'
PLACE_ID = 'place_id'
NAME = 'name'
VICINITY = 'vicinity'

# Google URL Shortener API fields
ID = 'id'

# Other fields
COUNT = 'count'
CLUSTERS = 'clusters'

# Google API URLS
GOOGLE_GEOCODE = 'https://maps.googleapis.com/maps/api/geocode/json?latlng=%s,%s&location_type=ROOFTOP&key=%s'
GOOGLE_PLACES = 'https://maps.googleapis.com/maps/api/place/nearbysearch/json?location=%s,%s&radius=%d&type=establishment&key=%s'
GOOGLE_MAPS = 'https://maps.googleapis.com/maps/api/staticmap?center=%s,%s&zoom=16&scale=2&size=400x400&%s&key=%s'
GOOGLE_MAPS_MARKER = 'markers=color:%s|%s,%s'
GOOGLE_SHORT_URL = 'https://www.googleapis.com/urlshortener/v1/url?key=%s'

# TODO change this, maybe return top N places instead
MIN_OCCUR_THRESHOLD = 500
MAX_ACCURACY_DISTANCE = 100 # meters
MAX_GROUP_DISTANCE = 500
GOOGLE_PLACES_RADIUS = 100

MAX_SUGGESTIONS = 10
CLUSTER_MARKER_COLOR = '0xff9900'
GROUP_MARKER_COLOR = 'red'


def main():
    start_time = time.time()
    args = parse_args()
    locations = import_data(args.takeout)
    clusters, groups = learn_places(locations, args.write)

    print "\nClusters:"
    if args.write:
        clusters_file = open('clusters.csv', 'w')
        clusters_file.write("Latitude, Longitude, Count\n")
    for i in xrange(len(clusters)):
        print '%3d. (%9.4f, %9.4f)  %-6d' % (i+1, clusters[i][LAT], clusters[i][LNG], clusters[i][COUNT])
        if args.write:
            clusters_file.write('%s, %s, %s\n' % (clusters[i][LAT], clusters[i][LNG], clusters[i][COUNT]))
    if args.write:        
        clusters_file.close()

    # print "\n" + get_suggestions(decode_coordinate(centers[1][0]), decode_coordinate(centers[1][1]))

    # TODO fix printing
    print "\nGroups:"
    if args.write:
        groups_file = open('groups.csv', 'w')
        groups_file.write("Latitude, Longitude, Count\n")
    for i in xrange(len(groups)):
        print '%3d. (%9.4f, %9.4f)  %-6d  %s' % (i + 1, groups[i][LAT], groups[i][LNG], groups[i][COUNT], groups[i][CLUSTERS])
        if args.write:
            groups_file.write('%s, %s, %s\n' % (groups[i][LAT], groups[i][LNG], groups[i][COUNT]))
    if args.write:
        groups_file.close()
    
    print "\nTime elapsed: %d seconds" % (time.time() - start_time)

    print '\n'
    for i in xrange(len(groups)):
        raw_input("Group %d:" % (i + 1))
        group = groups[i]
        webbrowser.open(get_map_url(group, i, clusters))
        print "Map: " + get_map_url(group, i, clusters)
        print ''
        print get_suggestions_str(get_suggestions(group[LAT], group[LNG]))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('file', metavar='file', help='Google location history JSON file')
    parser.add_argument('-w', '--write', dest='write', action='store_true', help='write learned data to csv files')
    return parser.parse_args()


def import_data(takeout_path):
    print "Importing takeout data..."
    takeout_file = open(takeout_path)
    takeout = json.loads(takeout_file.read())
    takeout_file.close()
    return takeout[LOCATIONS]


def learn_places(locations, write):
    print "Learning from %d location records..." % len(locations)
    
    locations_dict = {}
    timestamps_dict = {}
    for i in xrange(len(locations)):
        location = locations[i]
        if location[ACCURACY] > MAX_ACCURACY_DISTANCE:
            continue
        latitude = location[LATITUDEE7] / 1000
        longitude = location[LONGITUDEE7] / 1000
        for (dlat, dlng) in [(-1,0), (0,-1), (0,0), (0,1), (1,0)]:
                loc = (latitude + dlat, longitude + dlng)
                if loc in locations_dict:
                    locations_dict[loc] += 1
                else:
                    locations_dict[loc] = 1
    locations_dict = {loc: count for (loc, count) in locations_dict.items() if count > min(len(locations) / 1000, MIN_OCCUR_THRESHOLD)}

    if write:
        coordinates_file = open('coordinates.csv', 'w')
        coordinates_file.write("Latitude, Longitude, Count\n")
        for loc in locations_dict:
            coordinates_file.write('%s, %s, %s, 0\n' % (float(decimal.Decimal(loc[0]).scaleb(-4)),
                                                        float(decimal.Decimal(loc[1]).scaleb(-4)), locations_dict[loc]))
        coordinates_file.close()

    clusters = get_clusters(locations_dict)
    groups = get_groups(clusters)

    return clusters, groups


def get_clusters(locations_dict):
    locations = set(locations_dict.keys())
    clusters = []
    stack = []
    while locations:
        stack.append(locations.pop())
        latitude_sum = 0
        longitude_sum = 0
        count_sum = 0
        points = []
        while stack:
            location = stack.pop()
            points.append(location)
            latitude, longitude = location
            count = locations_dict[location]
            count_sum += count
            latitude_sum += latitude * count
            longitude_sum += longitude * count
            for (dlat, dlng) in [(-1,-1), (-1,0), (-1,1), (0,-1),
                                 (0,1), (1,-1), (1,0), (1,1)]:
                loc = (latitude + dlat, longitude+ dlng)
                if loc in locations:
                    stack.append(loc)
                    locations.remove(loc)
        clusters.append({LAT: (latitude_sum / 10000) / float(count_sum),
                         LNG: (longitude_sum / 10000) / float(count_sum),
                         COUNT: count,
                         LOCATIONS: points})
    return sorted(clusters, key=lambda cluster: cluster[COUNT], reverse=True)


def get_groups(clusters):
    distances = get_distances(clusters)
    groups = []
    ungrouped = range(len(clusters))
    while ungrouped:
        group = sorted(get_group(ungrouped.pop(0), distances, ungrouped))
        count = sum([clusters[i][COUNT] for i in group])
        groups.append({LAT: sum([clusters[i][LAT] * clusters[i][COUNT] for i in group]) / count,
                       LNG: sum([clusters[i][LNG] * clusters[i][COUNT] for i in group]) / count,
                       COUNT: count,
                       CLUSTERS: group})
    return sorted(groups, key=lambda group: group[COUNT], reverse=True)


def get_group(i, distances, ungrouped):
    group = [i]
    for j in ungrouped:
        if distances[i][j] <= MAX_GROUP_DISTANCE:
            ungrouped.remove(j)
            group += get_group(j, distances, ungrouped)
    return group


def get_distances(clusters):
    distances = [[0] * len(clusters) for i in xrange(len(clusters))]
    for i in xrange(len(clusters)):
        for j in xrange(len(clusters)):
            if i != j:
                distance = get_distance(clusters[i], clusters[j])
                distances[i][j] = distance
                distances[j][i] = distance
    return distances


def get_distance(cluster1, cluster2):
    dlat = abs(cluster1[LAT] - cluster2[LAT])
    dlng = abs(cluster1[LNG] - cluster2[LNG])
    lat_distance = dlat * LAT_DISTANCE
    lng_distance = dlng * LNG_DISTANCE * math.cos((cluster1[LAT] + cluster2[LAT]) / 2)
    return math.sqrt(math.pow(lat_distance, 2) + math.pow(lng_distance, 2))


def get_map_url(group, group_num, clusters):
    markers = []
    markers.append(get_map_marker(group[LAT], group[LNG], GROUP_MARKER_COLOR))
    group_clusters = group[CLUSTERS]
    for i in xrange(len(group_clusters)):
        index = group_clusters[i]
        cluster = clusters[index]
        markers.append(get_map_marker(cluster[LAT], cluster[LNG], CLUSTER_MARKER_COLOR))
    return get_short_url(GOOGLE_MAPS % (group[LAT], group[LNG], '&'.join(markers), API_KEY))


def get_map_marker(latitude, longitude, color):
    return GOOGLE_MAPS_MARKER % (color, latitude, longitude)


def get_short_url(url):
    request = urllib2.Request(GOOGLE_SHORT_URL % API_KEY, '{"longUrl": "%s"}' % url, {'Content-Type': 'application/json'})
    response = json.load(urllib2.urlopen(request))
    return response[ID]


def get_suggestions(latitude, longitude):
    return get_geocode(latitude, longitude) + get_places(latitude, longitude)


def get_suggestions_str(suggestions):
    suggestions_str = ''
    for i in xrange(len(suggestions)):
        suggestion = suggestions[i]
        suggestions_str += "%s. " % string.ascii_uppercase[i]
        suggestions_str += "%s\n" % suggestion[NAME]
        if VICINITY in suggestion:
            suggestions_str += "   %s\n" % suggestion[VICINITY]
        suggestions_str += "\n"
    return suggestions_str


def get_geocode(latitude, longitude):
    response = json.load(urllib2.urlopen(GOOGLE_GEOCODE % (latitude, longitude, API_KEY)))
    results = response[RESULTS]
    geocode = []
    if results:
        result = results[0]
        geocode.append({NAME: result[FORMATTED_ADDRESS],
                       LAT: result[GEOMETRY][LOCATION][LAT],
                       LNG: result[GEOMETRY][LOCATION][LNG],
                       PLACE_ID: result[PLACE_ID]})
    return geocode


def get_places(latitude, longitude):
    response = json.load(urllib2.urlopen(GOOGLE_PLACES % (latitude, longitude, GOOGLE_PLACES_RADIUS, API_KEY)))
    results = response[RESULTS]
    places = []
    for result in results[:MAX_SUGGESTIONS - 1]:
        places.append({NAME: result[NAME],
                       VICINITY: result[VICINITY],
                       LAT: result[GEOMETRY][LOCATION][LAT],
                       LNG: result[GEOMETRY][LOCATION][LNG],
                       PLACE_ID: result[PLACE_ID]})
    return places


if __name__ == "__main__":
    main()