// --------------------------------------------------------------------------
// Licensed Materials - Property of IBM
//
// 5725-A06 5725-A29 5724-Y48 5724-Y49 5724-Y54 5724-Y55
// Copyright IBM Corporation 1998, 2022. All Rights Reserved.
//
// Note to U.S. Government Users Restricted Rights:
// Use, duplication or disclosure restricted by GSA ADP Schedule
// Contract with IBM Corp.
// --------------------------------------------------------------------------

/* ------------------------------------------------------------

Problem Description
-------------------


------------------------------------------------------------ */

using CP;

int H = ...;

// Reads in workers from data file
{string} Workers = ...;

// Reads in tasks from data file
{string} Tasks = ...;

// Task data
int Durations[Tasks] = ...;
int EarliestStart[Tasks] = ...; // Earliest start time for each task
int LatestEnd[Tasks] = ...;   // Latest end time for each task

// Mapping of workers and tasks they are able to do
tuple Skill {
  string worker;
  string task; 
};
{Skill} Skills = ...;


// Interval variable that has one per each task
dvar interval tasks[t in Tasks] in 0..H size Durations[t];
// Interval variable that goes through mapping of tasks/workers and assigns (unassigned will be zero interval)
dvar interval wtasks[s in Skills] optional;

// define an optional array of interval variables for each worker
dvar interval busyTime[w in Workers][s in Skills] optional;

// the sequence of tasks for each worker (the chart we normally look at)
dvar sequence busyTimes[w in Workers] in all(s in Skills: s.worker == w) busyTime[w][s];

// This will grab the start of the next interval
dexpr float nextIntervalStart[w in Workers][s in Skills] = presenceOf(busyTime[w][s])*startOfNext(busyTimes[w], busyTime[w][s], H);
dexpr float startOfFirst[w in Workers][s in Skills] = (endOfPrev(busyTimes[w], busyTime[w][s], 0) == 0) * (startOf(busyTime[w][s]));
	

dexpr float otherWorkerSlack[s in Skills] = presenceOf(wtasks[s])* sum(ski in Skills: ski.task == s.task) sum(sk in Skills: sk.worker == ski.worker) 
	(((minl(nextIntervalStart[sk.worker][sk],LatestEnd[s.task]) - endOf(busyTime[sk.worker][sk]))
  * (Durations[s.task] < (minl(nextIntervalStart[sk.worker][sk],LatestEnd[s.task]) - endOf(busyTime[sk.worker][sk]))))
//* ((Durations[s.task] < (startOfFirst[sk.worker][sk] - maxl(EarliestStart[s.task], 0)))|| (sk == s))));
  + ((startOfFirst[sk.worker][sk] - maxl(EarliestStart[s.task], 0)) 
  * (Durations[s.task] < (startOfFirst[sk.worker][sk] - maxl(EarliestStart[s.task], 0)))));
//* ((Durations[s.task] < (minl(nextIntervalStart[sk.worker][sk],LatestEnd[s.task]) - endOf(busyTime[sk.worker][sk])))|| (sk == s)))
	

//currently counting slack for scheduled window, for each worker, for each task
maximize sum(w in Workers) (sum(s in Skills:s.worker == w) (otherWorkerSlack[s]));

subject to {
  forall(t in Tasks) {
    // if tasks[t] is present in the solution, then exactly one of the interval variables in wtasks[s] will be present, and tasks[t] starts and ends together with this chosen interval.
    alternative(tasks[t], all(s in Skills: s.task==t) wtasks[s]); 
    // stay within bounds of task window
    endOf(tasks[t]) <= LatestEnd[t];
    startOf(tasks[t]) >= EarliestStart[t];
    endOf(tasks[t]) - startOf(tasks[t]) >= Durations[t];   
  }
  // No overlap for the workers
  forall(w in Workers) {
    noOverlap(all(s in Skills: s.worker==w) wtasks[s]);
    noOverlap(busyTimes[w]);
    forall(s in Skills: s.worker == w){
      // constrain worker intervals to align with wtasks
      startOf(busyTime[w][s]) == startOf(wtasks[s]);
      endOf(busyTime[w][s]) == endOf(wtasks[s]);
    }
  } 

};

execute {
		cp.param.FailLimit = 10000;
		for(s in Skills)
			if(wtasks[s].present){
				writeln(s.task + " is assigned to " + s.worker + " for interval " + wtasks[s].start + "-" + wtasks[s].end);
				//writeln(slck[s])
			}					
}
