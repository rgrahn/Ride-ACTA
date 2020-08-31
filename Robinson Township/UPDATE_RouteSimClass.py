from UPDATE_RouteRiderVanClass import *
import networkx as nx
import datetime as dt

class Sim(object):
    def __init__(self, startTime, vehicles, riders, graph, timeDict, waitCoeff, driveCoeff, timeWindow):
        self.time = startTime # Start time is at 6:00am
        self.vehiclesDict = vehicles
        self.vehicles = [ ]
        self.remainingRiders = riders
        self.dailyRiders = riders
        self.graph = graph
        self.systemQueue = [ ]
        self.timeDict = timeDict
        self.waitCoeff = waitCoeff
        self.driveCoeff = driveCoeff
        self.timeWindow = timeWindow
        self.uberRiders = uberQueue()
        
    def step(self):
        self.time += 5
        
    # Convert time to a timeperiod (e.g., 15min time intervals)
    def getTimePeriod(self, timeString):
        timeInterval = 15
        timePeriod = dt.datetime.strptime(timeString, '%H:%M:%S').time()
        timePeriod = str(timePeriod.replace(minute = timeInterval*(timePeriod.minute//timeInterval), second = 0))
        return timePeriod

    # Converts seconds to time string
    def convertSecondsToTimeString(self, seconds):
        hours = str(int(seconds//3600))
        minutes = str(int((seconds%3600)//60))
        if len(hours) < 2:
            hours = '0' + hours
        if len(minutes) < 2:
            minutes = '0' + minutes
        secs = '00'
        return ':'.join([hours, minutes, secs])

    # Activate vans based on their start times
    def activateVans(self):
        for veh, startTime in self.vehiclesDict.items():
            if (startTime <= self.time) and ((startTime + 5) > self.time):
                self.vehicles.append(van(veh, 3, self.time))

    # Finds vehicle with minimum marginal cost
    def findMinCost(self, timePeriod, rider):
        marginalCosts = []
        routes = []
        for veh in self.vehicles:
            marginalCost, newRoute, riderPickup = veh.findBestRoute(self.graph[timePeriod], rider, \
                                                                    self.timeDict, self.waitCoeff, \
                                                                    self.driveCoeff, uberRiders=None)
            marginalCosts.append(marginalCost)
            routes.append(newRoute)
        bestIndex = marginalCosts.index(min(marginalCosts))
        self.vehicles[bestIndex].route = routes[bestIndex]
        self.vehicles[bestIndex].riderQueue.append(rider)
        rider.van = self.vehicles[bestIndex].vehID
        self.remainingRiders.remove(rider)

    
    def assignRiderToVan(self):
        maxWaitTime = 1000*60 # This defines the threshhold to assign an Uber to a given passenger
        for rider in self.remainingRiders:
            # Checks if rider is within the pre-defined time window
            if (rider.origTime <= self.time + self.timeWindow):
                timePeriod = self.getTimePeriod(self.convertSecondsToTimeString(self.time))
                # The case when only one vehicle is working
                if (len(self.vehicles) == 1):
                    marginalCost, newRoute, riderPickup = self.vehicles[0].findBestRoute(self.graph[timePeriod], rider, \
                                                                                      self.timeDict, self.waitCoeff, \
                                                                                      self.driveCoeff, uberRiders=None)
                    # If wait time for next rider is greater than defined max --> assign Uber
                    if (riderPickup - self.timeDict[rider.rideID]) > maxWaitTime:
                        self.uberRiders.uberQueue.append(rider)
                        self.remainingRiders.remove(rider)
                        rider.van = 'Uber'
                    else:
                        self.vehicles[0].riderQueue.append(rider)
                        rider.van = self.vehicles[0].vehID
                        self.remainingRiders.remove(rider)                                                          
                        self.vehicles[0].route = newRoute
                elif  (self.time >= 39600) and (self.time < 50400):
                        marginalCost, newRoute, riderPickup = self.vehicles[1].findBestRoute(self.graph[timePeriod], rider, \
                                                                                             self.timeDict, self.waitCoeff, \
                                                                                             self.driveCoeff, uberRiders=None)
                        self.vehicles[1].riderQueue.append(rider)
                        rider.van = self.vehicles[1].vehID
                        self.remainingRiders.remove(rider)                                                          
                        self.vehicles[1].route = newRoute
                else:
                    self.findMinCost(timePeriod, rider)

    # Makes the next trip for the van based on the vehicles pre-determined route
    def nextTrip(self):
        timePeriod = self.getTimePeriod(self.convertSecondsToTimeString(self.time))
        for veh in self.vehicles:
            if (veh.inTransit == False) and ((veh.departureTime == None) or (veh.departureTime <= self.time)):
                travTime = veh.getLinkTravTime(self.graph[timePeriod])
                veh.arrivalTime = self.time + travTime
                veh.inTransit = True


    # Moved the van between locations within the van's route
    def moveVans(self):
        for veh in self.vehicles:
            if (veh.arrivalTime <= self.time) and (veh.inTransit == True):
                veh.currentLocation = veh.route[0][1]
                veh.inTransit = False
                # The case when the vehicle has to dwell before pickup of next request in route
                # Takes max of arrival time and the request time   
                if (len(veh.route) >= 2):     
                    # No dwell if current location == next location
                    dwellTime = 60 if (veh.route[0][1] != veh.route[1][1]) else 0 
                if (len(veh.route[0]) == 3) and (veh.route[0][2] == 'pickup'):
                    # Case when next location is a pickup --> can't depart before request pickup time
                    veh.departureTime = max(veh.arrivalTime, self.timeDict[veh.route[0][0]]) + dwellTime
                elif (len(veh.route[0]) == 3) and (veh.route[0][2] == 'dropoff'):
                    # Case when next location is a dropoff --> add dwellTime
                    veh.departureTime = veh.arrivalTime + dwellTime
                else:
                    veh.departureTime = veh.arrivalTime
                veh.route.pop(0)
                veh.dropoffRiders(veh.arrivalTime)
                veh.pickupRiders(veh.departureTime)