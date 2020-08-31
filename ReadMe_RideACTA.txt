Robinson Township Simulation Folder - 

Data:
"1b_filteredTrajWithFreeway.csv" - Vehicle trajectory data used to compute existing service metrics. This is used to verify vehicle-to-rider matches.
				   Please contact Rick Grahn at rgrahn@andrew.cmu.edu for data due to large size.
"2f_finalRidershipHighwayFilter.csv" - Ridership data with input errors removed.
"3e_medTravTimes.csv" - Computed median travel times between nodes calculated from vehicle trajectory data.

Required Python Files:
"baseCaseSimulation.py" - Code to verify existing data and compute system performance based on provided data.
"vehicleMatching.py" - Used to verify shuttle-to-rider matches. Many input data errors were observed.
"UPDATE_RouteRiderVanClass.py" - defines rider and shuttle classes to be used in the simulation
"UPDATE_RouteSimClass.py" - defines simulation class used to simulate various operational strategies.

Simulation File:
Robinson_Simulation - This file is the run file to compute existing system performing using 'baseCaseSimulation.py' and 'vehicleMatching.py'.
		      This file is also used to run developed model to test various operational policies. Results and be output and compared.	

Moon Township Simulation Folder - 

Preliminary Code - 
"Demand_Sampling_Moon_Township.py" - File to generate simulated demand for Moon Township based on Robinson Township demand profile. Can generate 
				     demand for a given level of input demand (e.g, 30 requests/day).

Data: 
"googleTravTimes_REVISED.txt" - time dependent travel times for all locations in Moon Township obtained from Google API.
"All_Moon_Businesses_REVISED.csv" - list of Moon Business coordinates. This is used for demand sampling.
Output csv from 'Demand_Sampling_Moon_Township.py' is used as an input for the 'Moon_Township_Simulation' file. 

Required Python Files:
"MOON_RouteRiderVanClass.py" - defines rider and shuttle classes to be used in the simulation.
"MOON_RouteSimClass.py" - defines simulation class used to simulate various operational strategies.
"MOON_RouteRiderVanClassFixed.py" - defines rider and shuttle classes to be used in the simulation for the fixed-route scenario.
"MOON_RouteSimClassFixed.py" - defines simulation class used to simulate various operational strategies for the fixed-route scenario.

Simulation File:
"Moon_Township_Simulation.py" - This file is used to run simulation based on input expected demand for either the on-demand scenario or 
				the fixed-route scenario.