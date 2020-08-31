import pandas as pd
import math
import numpy as np
import matplotlib.pyplot as plt
import os
import datetime as dt
import time
import networkx as nx
import osmnx as ox
from itertools import permutations
import vehicleMatching as vm
from vehicleMatching import *

class rider(object):
    def __init__(self, rideID, origSec, pickupSec, origLat, origLong, dropoffSec, destLat, destLong, pickupLat, pickupLong):
        self.rideID = rideID
        self.origSec = origSec
        self.pickupSec = pickupSec
        self.origLat = origLat
        self.origLong = origLong
        self.dropoffSec = dropoffSec
        self.destLat = destLat
        self.destLong = destLong
        self.pickupLat = pickupLat
        self.pickupLong = pickupLong
        self.pickupTime = None
        self.dropoffTime = None

class van(object):
    def __init__(self, vehicle_id, currentLocation, currentTimeSec, trajData):
        self.vehicle_id = vehicle_id
        self.currentRiders = []
        self.currentLocation = currentLocation
        self.currentTimeSec = currentTimeSec
        self.trajData = trajData

    def addRider(self, rider):
        self.currentRiders.append(rider)
        
    def getRiders(self):
        riderList = []
        for rider in self.currentRiders:
            riderList.append(rider.rideID)    
        return riderList
    
    def getRiderDestList(self):
        destList = []
        for rider in self.currentRiders:
            destList.append(rider.dest)    
        return destList
    
    def getOrigTimePeriods(self):
        riderList = []
        for rider in self.currentRiders:
            riderList.append(rider.timePeriod)    
        return riderList

# ============================================================================    
# Calculates distance from t to t+1 for the van trajectories
def distFunc(data):
    reqFeetPerSec = 7.33 #corresponds to 5 mph
    a = data['latitude']
    b = data['longitude']
    c = data['latitude'].shift(-1)
    d = data['longitude'].shift(-1)
    data.loc[:,'dist'] = haversineVec(a, b, c, d)
    shiftTime = data['sec'].shift(-1)
    data.loc[:,'timeElapsed'] = shiftTime - data.loc[:,'sec']
    data.loc[:,'reqTravDist'] = data.loc[:,'timeElapsed'] * reqFeetPerSec
    return data

# If van is moving faster than 5mph between time steps, then consider the van moving
def moving(data):
    data.loc[:,'moving'] = 0
    data.loc[(data['dist'] > data['reqTravDist']), 'moving'] = 1
    return data

#  ==============    Creates a list of riders to be served for the given day   ==============================
#  ==============    and converts them to rider objects for the simulation     ==============================
def createDailyRiderList(riderData):
    riderList = []
    for i in range(len(riderData)):
        riderList.append(rider(riderData['ride_id'].iloc[i], riderData['orig_sec'].iloc[i], riderData['pickup_sec'].iloc[i],\
                               riderData['USE_orig_lat'].iloc[i], riderData['USE_orig_long'].iloc[i], riderData['drop_sec'].iloc[i],\
                               riderData['USE_dest_lat'].iloc[i], riderData['USE_dest_long'].iloc[i],\
                               riderData['pickup_lat'].iloc[i], riderData['pickup_long'].iloc[i]))
    # create a list of riders that need to be served where riders can be removed throughout the day
    remainingRiders = riderList.copy()
    return riderList, remainingRiders

#Used to calculate distances between coordinate points
def haversine(coord1, coord2):
    R = 6372800  # Earth radius in meters
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    
    phi1, phi2 = math.radians(lat1), math.radians(lat2) 
    dphi       = math.radians(lat2 - lat1)
    dlambda    = math.radians(lon2 - lon1)
    
    a = math.sin(dphi/2)**2 + \
        math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2*R*math.atan2(math.sqrt(a), math.sqrt(1 - a))*3.28084 #convert to feet

# Assign start times to only the new added van riders, not current riders
def assignStartTimes(van, time, newAddedRiders):
    if (newAddedRiders == []):
        return
    for rider in newAddedRiders:
        rider.pickupTime = time

def find_nearest(array, value):
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return idx

def checkForwardBackward(rider, filtTraj, idx):
    distBefore = haversine((rider.destLat, rider.destLong), tuple(filtTraj[['latitude','longitude']].iloc[idx - 1]))
    distAfter = haversine((rider.destLat, rider.destLong), tuple(filtTraj[['latitude','longitude']].iloc[idx + 1]))
    if (distBefore < distAfter):
        return 'Before'
    elif (distBefore > distAfter):
        return 'After'
    else:
        return None
    
# steps either forward or backward to find closest traj point to a given riders destination. If not inside buffer, then return None
def findClosestDist(rider, filtTraj, direction, idx):
    bufferRadius = 750
    if (direction == 'Before'):
        step = -1
    else: # After case
        step = +1
    i = 0
    while True:
        distCurrent = haversine((rider.destLat, rider.destLong), tuple(filtTraj[['latitude','longitude']].iloc[idx + i*step]))
        distBefOrAft = haversine((rider.destLat, rider.destLong), tuple(filtTraj[['latitude','longitude']].iloc[idx + (i+1)*step]))
        if(distBefOrAft < distCurrent):
            i += 1
        else:
            minIndex = idx + (i*step)
            distFinal = haversine((rider.destLat, rider.destLong), tuple(filtTraj[['latitude','longitude']].iloc[minIndex]))
            if (distFinal < bufferRadius):
                return minIndex
            else:
                return None   
            
def findAndAssignDropTimes(van, addedRiders):
    for rider in addedRiders:
        # Filter trajectory times for all times after the assigned pickup time
        filtTraj = van.trajData[van.trajData['sec'] >= rider.pickupTime].reset_index(drop=True).copy()    
        # Find index of closest trajectory point in time to the tabulated rider dropoff time
        idx = find_nearest(filtTraj['sec'], rider.dropoffSec)
        # Find coordinates at the specific time and calculate the distance from the van to the rider destination
        trajCoords = tuple(filtTraj[['latitude','longitude']].iloc[idx])
        dist = haversine((rider.destLat, rider.destLong), trajCoords)
        # Checks if dropoff location is feasible and assign a dropoff time
        bufferRadius = 750
        if (dist < bufferRadius):
            rider.dropoffTime = rider.dropoffSec
        else:
            # Check if nearby (forward or backward) points are closer to location and iterate until min value is found
            direction = checkForwardBackward(rider, filtTraj, idx)
            if (direction != None):
                minIndex = findClosestDist(rider, filtTraj, direction, idx)
                # If a location is found by stepping forward or backward within buffer radius, assign time with closest location
                if (minIndex != None):
                    rider.dropoffTime = filtTraj['sec'].iloc[minIndex]
                else:
                    rider.dropoffTime = None  
            else:
                rider.dropoffTime = None

def checkPickupTime(van, rider):
    # Are the origin and pickup coordinates close?
    distOrigCoordsToPickupCoords = haversine((rider.origLat, rider.origLong), (rider.pickupLat, rider.pickupLong))
    # Is the van close to the pickup coordinates at the same time?
    idx = find_nearest(van.trajData['sec'], rider.pickupSec)
    vanLocationAtPickupTime = tuple((van.trajData['latitude'].iloc[idx], van.trajData['longitude'].iloc[idx]))
    distVanToPickupCoords = haversine(van.currentLocation, vanLocationAtPickupTime)
    return distOrigCoordsToPickupCoords, distVanToPickupCoords
           
def findVanDepartureTime(van, rider):
    bufferRadius = 1000
    distOrigCoordsToPickupCoords, distVanToPickupCoords = checkPickupTime(van, rider)
    # if pickup coordinates are at the request dest and the van is nearby, assign pickuptimes to riders
    if (distOrigCoordsToPickupCoords < bufferRadius) and (distVanToPickupCoords < bufferRadius):
        currentLatestTime = rider.pickupSec
    # If van is nearby the origin before the departure time, assign departure time to van
    elif (van.currentTimeSec <= rider.origSec):
        currentLatestTime = rider.origSec  
    # If van arrives later, then assign van the current van time
    else:
        currentLatestTime = van.currentTimeSec
    # Finds the closest time in the trajectory file to the assigned time from above and check if the van is moving
    index = find_nearest(van.trajData['sec'], currentLatestTime)
    isMoving = van.trajData['moving'].iloc[index]
    if (isMoving == 1):
        latestTime = currentLatestTime
    else:
        while (van.trajData['moving'].iloc[index] == 0):
            index += 1
            latestTime = van.trajData['sec'].iloc[index]
    return latestTime
    
# Add riders from a specific location
def addRiders(van, remainingRiders, freeway):
    j = 0
    newAddedRiders = []
    currentLatestTime = -1
    while (len(remainingRiders) > 0):  
        if (j == len(remainingRiders)):
            return
        riderLocation = (remainingRiders[j].origLat, remainingRiders[j].origLong)
        riderOrigTime = remainingRiders[j].origSec
        vanDistToRider = haversine(van.currentLocation, riderLocation)
        # Define time window where riders can be picked up before their assigned time
        timeWindow = 300
        bufferRadius = 750
        if (riderOrigTime - timeWindow > van.currentTimeSec):
            return
        elif (vanDistToRider < bufferRadius) and (van.currentTimeSec >= (riderOrigTime - timeWindow)) and (freeway != 1):
            van.addRider(remainingRiders[j])
            newAddedRiders.append(remainingRiders[j])
            latestTime = findVanDepartureTime(van, remainingRiders[j])
            if (latestTime > currentLatestTime):
                currentLatestTime = latestTime
            remainingRiders.pop(j)       
        else:
            j += 1
            continue
        # After finding all potential pickups at a location, need to assign start times based on the last rider or van time
        assignStartTimes(van, currentLatestTime, newAddedRiders)
        # Assign dropoff times once riders have been added based on trajectory data
        findAndAssignDropTimes(van, newAddedRiders)
        newAddedRiders = []      
        
# Actually makes the dropoffs for the current van riders. 
def makeDropoff(van, freeway):
    bufferRadius = 750
    i = 0
    while (i < len(van.currentRiders)):
        # This is the case when dropoff times were already assigned at pickup
        if (van.currentRiders[i].dropoffTime != None):
            if (van.currentTimeSec >= van.currentRiders[i].dropoffTime):
                van.currentRiders.pop(i)
            else:
                i += 1
        else:
            # Case when dropoff times are not assigned at pickup 
            vanDistanceToDropoff = haversine((van.currentRiders[i].destLat, van.currentRiders[i].destLong), van.currentLocation)
            if (vanDistanceToDropoff < bufferRadius) and (freeway != 1) and (van.currentTimeSec >= van.currentRiders[i].pickupTime):
                filtTraj = van.trajData[van.trajData['sec'] >= van.currentTimeSec].reset_index(drop=True).copy() 
                direction = checkForwardBackward(van.currentRiders[i], filtTraj, 0)
                if (direction != None):
                    minIndex = findClosestDist(van.currentRiders[i], filtTraj, direction, 0)
                    van.currentRiders[i].dropoffTime = filtTraj['sec'].iloc[minIndex]
                    van.currentRiders.pop(i)
                else:
                    van.currentRiders[i].dropoffTime = van.currentTimeSec
                    van.currentRiders.pop(i)
            else:
                i += 1

                
# Run the simulation for a specific van and specific date
def completeCircuit(van, riderList, remainingRiders):
    for i, row in van.trajData.iterrows():
        van.currentLocation = tuple((row['latitude'],row['longitude']))
        van.currentTimeSec = row['sec']
        moving = row['moving'] 
        freeway = row['freeway']  
        addRiders(van, remainingRiders, freeway)
        if (len(van.currentRiders) > 0):
            makeDropoff(van, freeway)

            
# ================= Complete simulation for all vans ==========================
def runSimulation(trajInfo, riderInfo, vehNo):
    initialLocation = (trajInfo['latitude'].iloc[0], trajInfo['longitude'].iloc[0])
    startTime = trajInfo['sec'].iloc[0]
    vanID = 'van'+str(vehNo)
    vanID = van(vehNo, initialLocation, startTime, trajInfo[['latitude','longitude','sec','moving','freeway']]) 
    dailyRiders, remainingRiders = createDailyRiderList(riderInfo)
    completeCircuit(vanID, dailyRiders, remainingRiders)
    simResults = tabulateResults(riderInfo, dailyRiders, vehNo)
    return simResults

# ============================== Simulation post-processing ======================================

def filterVanForDaySimulation(vehNo, trajData, riderData):
    trajDF = trajData[['vehicle_id', 'latitude', 'longitude', 'datetime','date','sec','freeway']]
    filtTraj = trajDF[trajDF['vehicle_id'] == vehNo].reset_index(drop=True).copy()
    testTraj1= distFunc(filtTraj)
    testTraj = moving(testTraj1)

    df1 = riderData[['ride_id','vehicle','vanMatch','origin_timestamp','USE_orig_lat','USE_orig_long','USE_dest_lat','USE_dest_long',\
                      'orig_sec','pickup_lat','pickup_long','pickup_sec','drop_sec','noshow_trip']]
    testRider = df1[df1['vanMatch'] == vehNo].reset_index(drop=True).copy()
    return testTraj, testRider


def tabulateResults(riderData, dailyRidersByVeh, vehNo):
    a = riderData[riderData['vanMatch'] == vehNo].copy()
    a1 = a[['ride_id','vehicle','vanMatch','origin_timestamp','noshow_trip','USE_orig_lat','USE_orig_long',\
            'orig_sec','pickup_sec','drop_sec']].copy()
    b = []
    c = []
    for rider in dailyRidersByVeh:
        b.append(rider.pickupTime)
        c.append(rider.dropoffTime)
    
    a1['simPickup'] = b
    a1['simDropoff'] = c
    a1.loc[:,'waitTimeData'] = a1['pickup_sec'] - a1['orig_sec']
    a1.loc[:,'waitTimeSim'] = a1['simPickup'] - a1['orig_sec']
    a1.loc[:,'driveTimeData'] = a1['drop_sec'] - a1['pickup_sec']
    a1.loc[:,'driveTimeSim'] = a1['simDropoff'] - a1['simPickup']
    a1.loc[:,'pickupTimeDiff'] = a1['simPickup'] - a1['pickup_sec']
    a1.loc[:,'dropTimeDiff'] = a1['simDropoff'] - a1['drop_sec']
    a1.loc[:,'sumWaitDrive'] = a1['waitTimeSim'].abs() + a1['driveTimeSim'].abs()
    return a1

def dropTrips(resultsData):
    print('Length of simulation data: ', len(resultsData))
    # Drop trips with drive times > 1hr and NA values
    dropValues = resultsData[resultsData['driveTimeSim'] < 45*60].reset_index(drop=True).copy()
    print(f'The number of trip dropped from results > 45min drive time: {len(resultsData) - len(dropValues)}')
    dropValues1 = dropValues[dropValues['waitTimeSim'] < 90*60].reset_index(drop=True).copy()
    print(f'The number of trip dropped from results > 90min wait time: {len(dropValues) - len(dropValues1)}')
    requestsToConsider = list(dropValues1['ride_id'].unique())
    # Drop no-show trips
    #dropValues2 = dropValues[dropValues['noshow_trip'] != 1].reset_index(drop=True).copy()
    #print(f'The number of noshow trips dropped from results: {len(dropValues) - len(dropValues2)}')
    return dropValues1, requestsToConsider

def runBaseCase(riderData, trajData, trajIkeaVehs):
    count = 0
    for vehNo in trajIkeaVehs:
        testTraj, testRider = filterVanForDaySimulation(vehNo, trajData, riderData)
        simResults = runSimulation(testTraj, testRider, vehNo)
        if count == 0:
            fullSimResults = simResults.copy()
            count += 1
        else:
            fullSimResults = fullSimResults.append([simResults])
            fullSimSorted = fullSimResults.sort_values(by='orig_sec').reset_index(drop=True).copy()  
    finalResults, droppedRequests = dropTrips(fullSimSorted)
    print(len(finalResults))
    return finalResults, droppedRequests

def runBaseCaseForMultipleDates(trajData, riderData, dates, riderIkeaVehList, trajIkeaVehList):
    count = 0
    requestsDict = dict()
    for simulDate in dates:
        print('Date: ', simulDate)
        if (count == 0):
            riderData4, trajData1, trajIkeaVehs = matchVehForDate(trajData, riderData, simulDate, riderIkeaVehList, trajIkeaVehList)
            baseCaseResults, requestsToConsider = runBaseCase(riderData4, trajData1, trajIkeaVehs)
            requestsDict[str(simulDate)] = requestsToConsider
            count += 1
        else:
            riderData4, trajData1, trajIkeaVehs = matchVehForDate(trajData, riderData, simulDate, riderIkeaVehList, trajIkeaVehList)
            baseCaseResults1, requestsToConsider1 = runBaseCase(riderData4, trajData1, trajIkeaVehs)
            baseCaseResults = baseCaseResults.append([baseCaseResults1],sort=True)
            requestsDict[str(simulDate)] = requestsToConsider1
    return baseCaseResults, requestsDict