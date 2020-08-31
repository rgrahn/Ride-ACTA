import pandas as pd
import math
import numpy as np
import datetime as dt

# Define a basic Haversine distance formula
def haversineVec(lat1, lon1, lat2, lon2):
    MILES = 3959
    lat1, lon1, lat2, lon2 = map(np.deg2rad, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1 
    dlon = lon2 - lon1 
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a)) 
    total_miles = MILES * c
    return total_miles*5280 # convert to feet

def getIkeaVehIDs(trajData, riderData, riderIkeaVehList, trajIkeaVehList):
    trajList = []
    riderList = []
    uniqueTrajVeh = list(trajData['vehicle_id'].unique())
    for i in range(len(trajIkeaVehList)):
        if (trajIkeaVehList[i] in uniqueTrajVeh):
            trajList.append(trajIkeaVehList[i])
            riderList.append(riderIkeaVehList[i])
    return trajList, riderList

# Process data for specific date
def getDataForSpecificDate(trajData, riderData, simulDate, IkeaRiderVehicles, IkeaTrajVehicles):
    # Filter for specific date
    trajData1 = trajData[trajData['date'] == simulDate].reset_index(drop = True).copy()
    riderData1 = riderData[riderData['date'] == simulDate].reset_index(drop = True).copy()
    # Get ikea vehicles working on the specific date
    trajList, riderList = getIkeaVehIDs(trajData1, riderData1, IkeaRiderVehicles, IkeaTrajVehicles)
    # Filter data to only include the Ikea vehicles
    trajData2 = trajData1[(trajData1['vehicle_id']).isin(trajList)].sort_values(by='datetime').reset_index(drop = True).copy()
    riderData2 = riderData1[(riderData1['vehicle']).isin(riderList)].sort_values(by='origin_timestamp').reset_index(drop = True).copy()
    return trajData2, riderData2, trajList, riderList


# Finds the first time the trajectory data is within a 750-radius of either the rider's pickup or dropoff locations
def findFirstClosestTime(trajData, riderLat, riderLong):
    bufferRadius = 750
    for i in range(len(trajData)):
        dist = haversineVec(riderLat, riderLong, trajData['latitude'].iloc[i], trajData['longitude'].iloc[i])
        if (dist <= bufferRadius):
            return dist, trajData['datetime'].iloc[i]
    return 'nf', 'nf'

def calculateTrajDist(trajData, vehID, riderData):
    riderData['origDist_' + str(vehID)] = 'NA'
    riderData['origVanTime_' + str(vehID)] = 'NA'
    riderData['destDist_' + str(vehID)] = 'NA'
    riderData['destVanTime_' + str(vehID)] = 'NA'
    traj = trajData[trajData['vehicle_id'] == vehID].sort_values(by='datetime').reset_index(drop = True).copy()
    for i in range(len(riderData)):
        origTime = riderData['origin_timestamp'].iloc[i] - pd.Timedelta(minutes = 3)
        filtTraj = traj[traj['datetime'] >= origTime]
        riderOrigLat, riderOrigLong = riderData['origin_latitude'].iloc[i], riderData['origin_longitude'].iloc[i]
        riderDestLat, riderDestLong = riderData['destination_latitude'].iloc[i], riderData['destination_longitude'].iloc[i]
        # returns van distance and time of van when at closest point to either rider pickup or dropoff
        origDist, vanTimeOrig = findFirstClosestTime(filtTraj, riderOrigLat, riderOrigLong)
        riderData['origDist_' + str(vehID)].iloc[i] = origDist
        riderData['origVanTime_' + str(vehID)].iloc[i] = vanTimeOrig
        if (vanTimeOrig != 'nf'):
            filtTraj1 = traj[traj['datetime'] >= vanTimeOrig]
            destDist, vanTimeDest = findFirstClosestTime(filtTraj1, riderDestLat, riderDestLong)
            riderData['destDist_' + str(vehID)].iloc[i] = origDist
            riderData['destVanTime_' + str(vehID)].iloc[i] = vanTimeDest
        else:
            riderData['destDist_' + str(vehID)].iloc[i] = 'nf'
            riderData['destVanTime_' + str(vehID)].iloc[i] = 'nf'
    return riderData

def subtractTime(column1, column2):
    if (column1 != 'nf') and (column2 != 'nf'):
        a = (column1.hour*3600 + column1.minute*60 + column1.second) - (column2.hour*3600 + column2.minute*60 + column2.second)
        return a / 60
    return 1000

# Need to determine the vehicles that serve IKEA and remove the vehicle that serves the West Busway
def multipleVehDist(vehList, trajData, riderData):
    for veh in vehList:
        riderData = calculateTrajDist(trajData, veh, riderData)
    return riderData

def vanMatching(riderData, vehList):
    for i in range(len(vehList)):
        # Calculate the waittime
        riderData.loc[:,'waitTimeData_' + str(vehList[i])] = \
            riderData.apply(lambda row: subtractTime(row['origVanTime_' + str(vehList[i])], \
                                                     row['origin_timestamp']), axis = 1)
        # Calculate the drive time
        riderData.loc[:,'driveTimeData_' + str(vehList[i])] = \
            riderData.apply(lambda row: subtractTime(row['destVanTime_' + str(vehList[i])], \
                                                     row['origVanTime_' + str(vehList[i])]), axis = 1)
        # Calculate the sum of the wait time and drive time
        riderData.loc[:,'sum_' + str(vehList[i])] = \
            riderData['waitTimeData_' + str(vehList[i])] + riderData['driveTimeData_' + str(vehList[i])]
    if len(vehList) == 2:
        vehStr0 = 'sum_'+str(vehList[0])
        vehStr1 = 'sum_'+str(vehList[1])
        riderData.loc[ riderData[vehStr0] < riderData[vehStr1], 'vanMatch'] = str(vehList[0])
        riderData.loc[ riderData[vehStr0] > riderData[vehStr1], 'vanMatch'] = str(vehList[1])
        riderData1 = riderData[(riderData[vehStr0] < 90) | (riderData[vehStr1] < 90)].reset_index(drop=True).copy()
        removedData = riderData[(riderData[vehStr0] > 90) & (riderData[vehStr1] > 90)].reset_index(drop=True).copy()
    elif len(vehList) == 3:
        vehStr0 = 'sum_'+str(vehList[0])
        vehStr1 = 'sum_'+str(vehList[1])
        vehStr2 = 'sum_'+str(vehList[2])
        riderData.loc[(riderData[vehStr0] < riderData[vehStr1]) & (riderData[vehStr0] < riderData[vehStr2]), 'vanMatch'] = str(vehList[0])
        riderData.loc[(riderData[vehStr1] < riderData[vehStr0]) & (riderData[vehStr1] < riderData[vehStr2]), 'vanMatch'] = str(vehList[1])
        riderData.loc[(riderData[vehStr2] < riderData[vehStr0]) & (riderData[vehStr2] < riderData[vehStr1]), 'vanMatch'] = str(vehList[2])    
        riderData1 = riderData[(riderData[vehStr0]<90)|(riderData[vehStr1]<90)|(riderData[vehStr2]<90)].reset_index(drop=True).copy()
        removedData = riderData[(riderData[vehStr0]>90)&(riderData[vehStr1]>90)&(riderData[vehStr2]>90)].reset_index(drop=True).copy()
    else:
        print('Check vehicles for day!')
    print(f'Count of dropped riders from matching process: {len(removedData)}')
    return riderData1, removedData

def firstLevelVanMatching(riderData, IkeaRiderVehicles, IkeaTrajVehicles):
    riderData['dist_d'] = riderData.apply(lambda row: haversineVec(row['destination_latitude'], row['destination_longitude'], \
                                                 row['dropoff_lat'], row['dropoff_long']), axis = 1)
    riderData['dist_o'] = riderData.apply(lambda row: haversineVec(row['origin_latitude'], row['origin_longitude'], \
                                                 row['pickup_lat'], row['pickup_long']), axis = 1)
    # If van location at pickup and dropoff less than 1000-ft, confirm request-van pairing
    matchedDF = riderData[(riderData['dist_d'] <= 1000) & (riderData['dist_o'] <= 1000)].copy()
    if (len(IkeaRiderVehicles) != len(IkeaTrajVehicles)):
        return print('Number of vehicles differ between traj and rider files!')
    else:
        for i in range(len(IkeaRiderVehicles)):
            matchedDF.loc[matchedDF['vehicle'] == IkeaRiderVehicles[i], 'vanMatch'] = IkeaTrajVehicles[i]
    nonMatchedDF = riderData[(riderData['dist_d'] > 1000) | (riderData['dist_o'] > 1000)].copy()
    return matchedDF, nonMatchedDF

def matchVehForDate(trajData, riderData, simulDate, IkeaRiderVehicles, IkeaTrajVehicles):
    # Process data for specific date
    trajData1, riderData1, trajIkeaVehs, riderIkeaVehs = getDataForSpecificDate(trajData, riderData, simulDate, \
                                                                            IkeaRiderVehicles, IkeaTrajVehicles)
    # Match vans to requests based on the distance between the rider dropoff coords and rider destination coords
    matchedRider, unmatchedRider = firstLevelVanMatching(riderData1, IkeaRiderVehicles, IkeaTrajVehicles)
    # Calculate distances from each trajectory van to the rider orig and destination coordinates for the unmatched riders
    riderData2 = multipleVehDist(IkeaTrajVehicles, trajData1, unmatchedRider)
    # Match vans to riders based on the min(sum(wait time + driving time))
    riderData3, removedData = vanMatching(riderData2, IkeaTrajVehicles)
    # Combined the two matched dataframes
    matchedDF = pd.DataFrame(columns = matchedRider.columns)
    riderData4 = matchedDF.append([matchedRider, riderData3]).sort_values(by='orig_sec').reset_index(drop=True).copy()
    riderData4 = riderData4.dropna(subset=['vanMatch'])
    riderData4['vanMatch'] = riderData4['vanMatch'].astype(int)
    return riderData4, trajData1, list(riderData4['vanMatch'].unique())