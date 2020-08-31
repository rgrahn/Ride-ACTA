import networkx as nx
import datetime as dt
import copy

class rider(object):
    def __init__(self, rideID, origTime, pendingTime, orig, dest, timePeriod, USE_orig_lat, 
                 USE_orig_long, USE_dest_lat, USE_dest_long):
        self.rideID = rideID
        self.origTime = origTime
        self.pendingTime = pendingTime
        self.orig = orig
        self.dest = dest
        self.timePeriod = timePeriod
        self.origCoords = (USE_orig_lat, USE_orig_long)
        self.destCoords = (USE_dest_lat, USE_dest_long)
        self.pickupTime = None
        self.dropoffTime = None
        self.origTimeString = self.convertSecondsToTimeString(origTime)
        self.van = None
        self.routeAssign = False

    # Convert seconds to time format (e.g., 08:03)
    def convertSecondsToTimeString(self, seconds):
        hours = str(int(seconds//3600))
        minutes = str(int((seconds%3600)//60))
        if len(hours) < 2:
            hours = '0' + hours
        if len(minutes) < 2:
            minutes = '0' + minutes
        secs = '00'
        return ':'.join([hours, minutes, secs])

class uberQueue(object):
    def __init__(self):
        self.uberQueue = []

class van(object):
    def __init__(self, vehID, currentLocation, startTime):
        self.vehID = vehID
        self.currentRiders = []
        self.riderQueue = []
        self.currentLocation = currentLocation
        self.startTime = startTime
        self.currentTime = startTime # Initialize to start time
        self.currentTimeString = self.convertSecondsToTimeString(startTime)
        self.route = [('idle', 3)]
        self.routeWaitTime = None
        self.inTransit = False
        self.departureTime = startTime
        self.arrivalTime = None

        
    def convertSecondsToTimeString(self, seconds):
        hours = str(int(seconds//3600))
        minutes = str(int((seconds%3600)//60))
        if len(hours) < 2:
            hours = '0' + hours
        if len(minutes) < 2:
            minutes = '0' + minutes
        secs = '00'
        return ':'.join([hours, minutes, secs])
    
    def addRiderToVan(self, rider):
        self.currentRiders.append(rider)
        self.riderQueue.remove(rider)

    def addRiderToVanQueue(self, rider):
        self.riderQueue.append(rider)

    def dropRider(self, rider):
        self.currentRiders.remove(rider)

    # Returns the shortest path and route segments for a source and target node
    def getTripInfo(self, orig, dest, graph):
        route = nx.shortest_path(graph, source = orig, target = dest, weight = 'median_x')
        shortestPathTime = nx.shortest_path_length(graph, source = orig, target = dest, weight = 'median_x')
        return shortestPathTime, route

    # Pickup riders from a location and remove rider from vanQueue
    def pickupRiders(self, deptTime):
        dwellTime = 60
        if (self.inTransit == False):
            for rider in self.riderQueue:
                if (rider.orig == self.currentLocation) and (rider.origTime <= deptTime):
                    self.addRiderToVan(rider)
                    rider.pickupTime = max(deptTime - dwellTime, rider.origTime)

    def getRiderIDsInRoute(self):
        rideIDs = []
        for stop in self.route:
            rideIDs.append(stop[0])
        return rideIDs
    
    # Dropoff riders at a specific location
    def dropoffRiders(self, arrivalTime):
        if (self.inTransit == False):
            ridersToDrop = []
            # Need to assign dropoffTimes for the van riders
            for rider in self.currentRiders:
                if (rider.dest == self.currentLocation) and (rider.rideID not in self.getRiderIDsInRoute()):
                    rider.dropoffTime = arrivalTime
                    ridersToDrop.append(rider)
            # Need to remove the riders from the van after dropoff
            for rider in ridersToDrop:
                self.dropRider(rider)

    def getPickupTime(self, riderID):
        for rider in self.currentRiders:
            if (rider.rideID == riderID):
                return rider.pickupTime

    # Calculates the travel time of a specific route based on the types of stops ('pickup', 'dropoff')     
    def calculateTravTime(self, startTime, route1, graph, timeDict):
        dwellTime = 60
        pickupTimes = dict()
        dropoffTimes = dict()
        route = copy.copy(route1)
        route.insert(0, ('currentLocation', self.currentLocation))
        departureTime = startTime
        for i in range(len(route)-1):
            currentLoc = route[i][1]
            nextLoc = route[i+1][1]
            pathTime = nx.shortest_path_length(graph, source = currentLoc, target = nextLoc, weight = 'median_x')
            arrivalTime = departureTime + pathTime
            # Determines the next node departure time based on next rider pickup and van arrival time and dwell time
            dwellTime = 60 if (route[i][1] != route[i+1][1]) else 0
            if (route[i+1][0] != 'idle') and (arrivalTime < timeDict[route[i+1][0]]) and (route[i+1][2] == 'pickup'):
                departureTime = timeDict[route[i+1][0]] + dwellTime
            elif (route[i+1][0] != 'idle') and (route[i+1][2] == 'dropoff'):
                departureTime = arrivalTime + dwellTime
            else:
                departureTime = arrivalTime 
            # Stores the pickup and dropoff times for each rider
            if (len(route[i+1]) == 3) and (route[i+1][2] == 'pickup'):
                pickupTimes[route[i+1][0]] = departureTime
            if (len(route[i+1]) == 3) and (route[i+1][2] == 'dropoff'):
                dropoffTimes[route[i+1][0]] = departureTime
        return departureTime, pickupTimes, dropoffTimes


    # Calculates wait and drive time lists for a given route.
    # Used to determine the best route based on the 'wait' and 'drive' coefficients
    def getWaitDriveTimes(self, pickupTimes, dropoffTimes, timeDict):
        totWaitTime = 0
        totDriveTime = 0
        maxWaitTime = 30*60
        maxDriveTime = 30*60
        for key in dropoffTimes.keys():
            if (key not in pickupTimes.keys()):
                riderPickupTime = self.getPickupTime(key) if self.getPickupTime(key) else self.departureTime
                pickupTimes[key] = riderPickupTime
            waitTime = pickupTimes[key] - timeDict[key]
            waitTime1 = waitTime if waitTime <= maxWaitTime else 99999
            driveTime = dropoffTimes[key] - pickupTimes[key]
            driveTime1 = driveTime if driveTime <= maxDriveTime else 99999
            totWaitTime += waitTime1
            totDriveTime += driveTime1
        return totWaitTime, totDriveTime

    # Gets the current route cost before added a new rider
    def getBaseCost(self, newRoute, graph, timeDict, coeffWait, coeffDrive):
        totTime, pickupTimes, dropoffTimes = self.calculateTravTime(self.departureTime, newRoute, graph, timeDict)
        waitTime, driveTime = self.getWaitDriveTimes(pickupTimes, dropoffTimes, timeDict)
        baseCost = coeffWait*waitTime + coeffDrive*driveTime
        return baseCost, waitTime

    # Find the best route by inserting new rider's orig/dest into existing route
    def findBestRoute(self, graph, rider, timeDict, coeffWait, coeffDrive, uberRiders=None):
        ikea = 3
        storeRoutes, storeWaitTimes, storeDriveTimes, totalTravTime, storePickup = [], [], [], [], []
        newRoute = copy.copy(self.route)
        # Calculate the base cost before inserting new rider
        baseCost, waitTime = self.getBaseCost(newRoute, graph, timeDict, coeffWait, coeffDrive)
        # First iter: instert orig stop into current route
        if (self.route[0][0] == 'idle') or (self.inTransit == True):
            startIndex = 1
        elif ((len(self.route) > 1) and (self.route[1][0] == 'idle')):
            startIndex = 2
        else:
            startIndex = 0
        for i in range(startIndex, len(newRoute)+1):
            newRoute.insert(i, (rider.rideID, rider.orig, 'pickup'))
            # Second iter: insert dest stop AFTER the orig stop
            for j in range(i+1, len(newRoute)+1):
                newRoute.insert(j, (rider.rideID, rider.dest, 'dropoff'))
                totTime, pickupTimes, dropoffTimes = self.calculateTravTime(self.departureTime, newRoute, graph, timeDict)
                storePickup.append(pickupTimes[rider.rideID])
                waitTime, driveTime = self.getWaitDriveTimes(pickupTimes, dropoffTimes, timeDict)
                storeWaitTimes.append(waitTime)
                storeDriveTimes.append(driveTime)
                storeRoutes.append(copy.copy(newRoute))
                totalTravTime.append(totTime)
                newRoute.pop(j)
            newRoute.pop(i)
        waitList = [i*coeffWait for i in storeWaitTimes]
        driveList = [i*coeffDrive for i in storeDriveTimes]
        sumList = [sum(x) for x in zip(waitList, driveList)]
        bestIndex = sumList.index(min(sumList))
        totalCost = sumList[bestIndex]
        marginalCost = totalCost - baseCost
        bestRoute = storeRoutes[bestIndex]
        riderPickup = storePickup[bestIndex]
        return marginalCost, bestRoute, riderPickup

    # This is used to step through the detailed route. It determines the travel time
    # for each link between nodes
    def getLinkTravTime(self, graph):
        ikea = 3
        #if (len(self.route) == 1) and (self.route[0][1] == ikea):
        if (len(self.route) == 1):
            self.route.append(('idle', self.route[0][1]))
        travTime, route = self.getTripInfo(self.currentLocation, self.route[0][1], graph)
        return travTime
