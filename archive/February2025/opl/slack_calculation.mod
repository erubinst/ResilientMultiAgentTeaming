/*********************************************
 * OPL 22.1.1.0 Model
 * Author: esmerubinstein
 * Creation Date: Aug 15, 2024 at 1:17:17 PM
 *********************************************/

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

tuple Precedence {
   string pre;
   string post;
};

int nTypes = ...;
range tTypes = 0..nTypes-1;

// Mapping of workers and tasks they are able to do
tuple Skill {
  string worker;
  string task; 
  int level;
  int type;
  int needsOA;
};
{Skill} Skills = ...;

{Precedence} Precedences = ...;

// Time in between each task (current model adds time for tasks that take place outside the house)
int DrivingTimes[tTypes][tTypes] = ...;

// Set of break start and end times
tuple Break {
  int start;
  int end;
};
{Break} Breaks[Workers] = ...;

tuple ListedBreak {
  string worker;
  int start;
  int end;
};

{ListedBreak} ListedBreaks = ...; 

tuple Step {
  int v;
  key int x;
};

sorted {Step} Steps[w in Workers] = 
   { <100, b.start> | b in Breaks[w] } union 
   { <0, b.end>   | b in Breaks[w] };
   
stepFunction Calendar[w in Workers] = 
  stepwise (s in Steps[w]) { s.v -> s.x; 100 };
  
{int} unionOfStartTimes = {b.start | b in ListedBreaks};

tuple triplet { int t1; int t2; int v; }
{triplet} transitionTimes = { <i,j, DrivingTimes[i][j]> | i in tTypes, j in tTypes };

// Interval variable that has one per each task
dvar interval tasks[t in Tasks] in 0..H size Durations[t];
// Interval variable that goes through mapping of tasks/workers and assigns (unassigned will be zero interval)
dvar interval wtasks[s in Skills] optional;

dvar interval travelTasks[t in Tasks] in 0..H;

//Difference between a break and its next break
dexpr int breakAfterBreakDifference[w in Workers][b in unionOfStartTimes] = sum(br in Breaks[w]: br.start == b) 
	min(bre in Breaks[w]: bre != br) 
		(
		(((bre.start - br.end) >= 0) 
		* (bre.start - br.end))
		
		+ (((bre.start - br.end) < 0)
		* H)
	);
	
//Start of the next break after break 
dexpr int breakStartAfterBreak[w in Workers][b in unionOfStartTimes] = sum(br in Breaks[w]: br.start == b)
    (sum(bre in Breaks[w]: bre != br)
    (((bre.start - br.end) == breakAfterBreakDifference[w][br.start])
	* (breakAfterBreakDifference[w][br.start] != H)
	* bre.start));
	
//Tasks in between boolean - will be 1 if there are tasks in between two breaks
dexpr int tasksInBetweenBreaks[w in Workers][b in unionOfStartTimes] = sum(br in Breaks[w]: br.start == b)
	sum(s in Skills:s.worker == w)
	(presenceOf(wtasks[s])
	* (startOf(wtasks[s]) <= breakStartAfterBreak[w][br.start])
	* (startOf(wtasks[s]) >= br.end));
	

//breakslots
dexpr int breakSlots[w in Workers][b in unionOfStartTimes] = sum(br in Breaks[w]: br.start == b)
	(breakStartAfterBreak[w][br.start] - br.end)
	* (breakStartAfterBreak[w][br.start] > 0)
	* (tasksInBetweenBreaks[w][br.start] == 0);
	
	
dvar sequence taskTimes[w in Workers] in all(s in Skills: s.worker == w) wtasks[s] 
	types all(s in Skills: s.worker ==w) s.type;

dexpr int minBreakDifference[s in Skills] =  presenceOf(wtasks[s])* min(b in Breaks[s.worker]) 
	(
		(((b.start - startOf(wtasks[s])) >= 0) 
		* (b.start - startOf(wtasks[s])))
		
		+ (((b.start - startOf(wtasks[s])) < 0)
		* H)
	);
	
dexpr int maxNegBreakDifference[s in Skills] = presenceOf(wtasks[s])* max(b in Breaks[s.worker]) 
	(
		(((b.end - startOf(wtasks[s])) <= 0) 
		* (b.end - startOf(wtasks[s])))
		
		+ (((b.end - startOf(wtasks[s])) > 0) 
		* -H)
		
	);

	
dexpr int nextBreakStart[s in Skills] = sum(b in Breaks[s.worker]) 
	(((b.start - startOf(wtasks[s])) == minBreakDifference[s])
	* (minBreakDifference[s] != H)
	* b.start);
	
dexpr int prevBreakEnd[s in Skills] = sum(b in Breaks[s.worker]) 
	(((b.end - startOf(wtasks[s])) == maxNegBreakDifference[s])
	* (minBreakDifference[s] != -H)
	* b.end);
	
dexpr int nextTaskStart[w in Workers][s in Skills] = presenceOf(wtasks[s])*(s.worker ==w)*startOfNext(taskTimes[w], wtasks[s], H);

dexpr int nextIntervalStart[s in Skills] = minl(nextTaskStart[s.worker][s], nextBreakStart[s]);
	
dexpr int allowedForWorker[w in Workers][t in Tasks] = sum(s in Skills: s.task == t)
	(s.worker == w);
	
dexpr int precendentExists[s in Skills][sk in Skills] = sum(p in Precedences)
	presenceOf(wtasks[s])
	* presenceOf(wtasks[sk])
	* (p.pre == sk.task)
	* (p.post == s.task);
	
dexpr int dependentExists[s in Skills][sk in Skills] = sum(p in Precedences)
	presenceOf(wtasks[s])
	* presenceOf(wtasks[sk])
	* (p.pre == s.task)
	* (p.post == sk.task);
	
// latest task that must precede s
dexpr int latestPrecedent[s in Skills] = presenceOf(wtasks[s])*max(sk in Skills) precendentExists[s][sk]*endOf(wtasks[sk]);

// earliest task that must come after s
dexpr int earliestDependent[s in Skills] = min(sk in Skills) 
	(
		(((dependentExists[s][sk]==1) && presenceOf(wtasks[sk]) && presenceOf(wtasks[s])) 
		* startOf(wtasks[sk]))
		
		+ (((dependentExists[s][sk] == 0) || !presenceOf(wtasks[sk]) || !presenceOf(wtasks[s]))
		* H)
	);
	
dexpr int travelBefore[s in Skills] = DrivingTimes[typeOfPrev(taskTimes[s.worker], wtasks[s], s.type)][s.type];
	
dexpr int individualTaskSlotSlack[s in Skills][sk in Skills] = 	(((minl(nextIntervalStart[sk],LatestEnd[s.task]) 
 	- maxl(maxl(prevBreakEnd[sk],maxl(endOf(wtasks[sk])), EarliestStart[s.task]),latestPrecedent[s]))
 	- (Durations[s.task] + DrivingTimes[s.type][sk.type] + DrivingTimes[s.type][typeOfPrev(taskTimes[sk.worker], wtasks[sk], s.type)]) + 1)
	* ((Durations[s.task] <= (minl(minl(nextIntervalStart[sk],LatestEnd[s.task]),earliestDependent[s]) 
	- maxl(maxl(prevBreakEnd[sk],maxl(endOf(wtasks[sk]), EarliestStart[s.task])),latestPrecedent[s])))
	&& (sk != s)));
	
dexpr int taskSlotSlack[s in Skills] = presenceOf(wtasks[s])* 
	sum(ski in Skills: ski.task == s.task) 
	sum(sk in Skills: sk.worker == ski.worker) individualTaskSlotSlack[s][sk]; 
	
dexpr int breakSlotSlack[w in Workers][s in Skills] = sum(b in Breaks[w])
	((((minl(minl(breakStartAfterBreak[w][b.start], LatestEnd[s.task]), earliestDependent[s])
	- maxl(maxl(b.end, EarliestStart[s.task]), latestPrecedent[s])) - Durations[s.task]) + 1)
	* (presenceOf(wtasks[s]))
	* (breakSlots[w][b.start] > 0)
	* (allowedForWorker[w][s.task] > 0)
	* ((minl(breakStartAfterBreak[w][b.start], LatestEnd[s.task])
	- maxl(b.end, EarliestStart[s.task])) >= Durations[s.task]));
	

dexpr int trueLatestEndsInFront[s in Skills][sk in Skills] = 
	  ((1 - ((startOf(wtasks[sk]) >= startOf(wtasks[s]))
	* (endOf(wtasks[sk]) <= nextBreakStart[s])
	* (presenceOf(wtasks[s])
	* presenceOf(wtasks[sk]))
	* (s.worker == sk.worker))) * (H)
	+ LatestEnd[sk.task]);
	
dexpr int slidingConstraint[s in Skills] = presenceOf(wtasks[s])
	* minl(minl(nextBreakStart[s],min(sk in Skills) minl(trueLatestEndsInFront[s][sk], LatestEnd[s.task])), earliestDependent[s]);
	
dexpr int tasksInFront[s in Skills] = sum(sk in Skills: sk.worker == s.worker) 
	  ((startOf(wtasks[sk]) >= endOf(wtasks[s]))
	* (startOf(wtasks[sk]) < slidingConstraint[s])
	* presenceOf(wtasks[s])
	* presenceOf(wtasks[sk])
	* (s != sk)
	* (minl(slidingConstraint[s], endOf(wtasks[sk])) - (startOf(wtasks[sk])+ travelBefore[sk])));
	
dexpr int forwardSlack[s in Skills] = presenceOf(wtasks[s])
	* (minl(slidingConstraint[s], LatestEnd[s.task]) - (tasksInFront[s] + endOf(wtasks[s])))
	* (nextBreakStart[s] > 0);
	
dexpr int totalBreakSlackForTask[s in Skills] = sum(w in Workers) breakSlotSlack[w][s];
	
dexpr int totalPreference = sum(s in Skills) presenceOf(wtasks[s])*s.level;

dexpr int totalSlack = sum(s in Skills) (taskSlotSlack[s] + forwardSlack[s] + totalBreakSlackForTask[s]);

//maximize staticLex(totalPreference, totalSlack); 

//dexpr float normalizedSlack = (totalSlack - 70)/(318-70);
//dexpr float normalizedPreference = (totalPreference - 32)/(65-32);

//maximize 0.42*normalizedSlack + 0.58*normalizedPreference;
//maximize totalSlack;
//minimize max(s in Skills) presenceOf(wtasks[s])*endOf(wtasks[s]);
int minAllowedPreference = ...;
int slackWeight = ...;
int preferenceWeight = ...;
//maximize slackWeight*totalSlack + preferenceWeight*totalPreference;
maximize totalSlack;

subject to {
    forall(t in Tasks) {
        // if tasks[t] is present in the solution, then exactly one of the interval variables in wtasks[s] will be present, and tasks[t] starts and ends together with this chosen interval.
        alternative(tasks[t], all(s in Skills: s.task==t) wtasks[s]); 
        
        // Task Window and Size Constraints
        endOf(tasks[t]) <= LatestEnd[t];
        startOf(tasks[t]) >= EarliestStart[t];
        (endOf(tasks[t]) - startOf(tasks[t])) >= Durations[t]; 
    }
    // Overlap Constraints
    forall(w in Workers) {
        noOverlap(all(s in Skills: s.worker==w) wtasks[s]);
        noOverlap(all(s in Skills: s.needsOA == 1) wtasks[s]);
        noOverlap(taskTimes[w]);
        noOverlap(taskTimes[w], transitionTimes);
    }
    // Availability Constraints
    forall(s in Skills) {
        forbidExtent(wtasks[s], Calendar[s.worker]);
    }
    // Precedence Constraints
    forall(p in Precedences) {
        endBeforeStart(tasks[p.pre], tasks[p.post]);
  	}  
  	totalPreference >= minAllowedPreference;
  	 
}

execute {
		cp.param.FailLimit = 10000;
		var f = new IloOplOutputFile("solution.csv");
		f.writeln("Worker,Task,Start,End,Forward Slack,Task Slot Slack,Break Slot Slack,Preference,Total Slack,Total Preference");
		f.writeln(",,,,,,,,", totalSlack, ",", totalPreference)
		for(s in Skills)
			f.writeln(s.worker,",",s.task,",",wtasks[s].start,",",wtasks[s].end,",",forwardSlack[s],",",taskSlotSlack[s], ",", totalBreakSlackForTask[s], ",", s.level);
		for(w in Workers)
			for(b in Breaks[w])
				f.writeln(w, ", break,", b.start, ",", b.end);
		f.close()	
		writeln("Total Slack", totalSlack);
		writeln("Total Preference", totalPreference);	
}


//main {
//  		thisOplModel.generate();
//  		var assignments  = thisOplModel;
//  		var def = assignments.modelDefinition;
//  		var data = assignments.dataElements;
//  		cp.solve();
//  		
//  		var max_preference = cp.getObjValue();
//  		data.minAllowedPreference = max_preference;
//  		data.slackWeight = 1;
//  		data.preferenceWeight = 0;
//  		thisOplModel.generate();
//		cp.solve()
//  		//opl1.postProcess();
//  		
//  		
//
//}