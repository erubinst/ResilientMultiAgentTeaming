/*********************************************
 * OPL 22.1.1.0 Model
 * Author: esmerubinstein
 * Creation Date: Dec 3, 2024 at 3:59:33 PM
 *********************************************/

 
 using CP;

// Horizon
int H = ...;

// Worker
tuple Worker {
  int worker_id;
  string worker;
};
{Worker} Workers = ...;

// Precedences between Requests
tuple Precedence {
   string pre;
   string post;
};
{Precedence} Precedences = ...;

// Tasks
tuple Task {
  int id;
  string task; 
  int duration;
  int start_location;
  int end_location;
  int est;
  int lft;
};
{Task} Tasks = ...;

// Request 
tuple Request {
  int request_id;
  string request;
};
{Request} Requests = ...;


// Tells which Tasks are in a Request
tuple Recipe {
  string request;
  string task;
};
{Recipe} Recipes = ...;


// Tells order of tasks within a request
tuple Dependency {
  string request;
  string task_b;
  string task_a;
};
{Dependency} Dependencies = ...;


tuple Skill{
  int skill_id;
  string skill;
}
{Skill} Skills = ...;


// Data structure linking for Tasks in a Request
tuple Operation {
  Request request;
  Task    task;
};
{Operation} Operations = 
  { <r, t> | r in Requests,  m in Recipes, t in Tasks : 
   r.request == m.request && t.task == m.task};


// Task and required skill 
tuple RequirementRaw {
  int id;
  int skill_id;
};
{RequirementRaw} RequirementsRaw = ...;


tuple Requirement {
  Operation operation;
  Skill skill;
};
{Requirement} Requirements = 
{ < o, s > | rr in RequirementsRaw, o in Operations, s in Skills: 
rr.id == o.task.id && rr.skill_id == s.skill_id};


// Worker and skill they have
tuple WorkerSkillRaw {
  int worker_id;
  int skill_id;
};
{WorkerSkillRaw} WorkerSkillsRaw = ...;


tuple WorkerSkill {
  Worker worker;
  Skill skill;
};
{WorkerSkill} WorkerSkills = 
{ < w, s > | wsr in WorkerSkillsRaw, w in Workers, s in Skills:
wsr.worker_id == w.worker_id && wsr.skill_id == s.skill_id };

// Every task/skill/worker combination
tuple AssignmentOption {
  WorkerSkill worker_skill;
  Requirement requirement;
};
{AssignmentOption} AssignmentOptions =
{ < ws, r > | ws in WorkerSkills, r in Requirements:
ws.skill.skill_id == r.skill.skill_id };

int nLocations = ...;
range tLocations = 0..nLocations-1;

// Duration matrix
int DrivingTimes[tLocations][tLocations] = ...;

// Set of break start and end times
tuple Break {
  int start;
  int end;
  int location;
};
{Break} Breaks[Workers] = ...;

tuple ListedBreak {
  string worker;
  int start;
  int end;
  int location;
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

dvar interval requestTimes[r in Requests] in 0..H;
dvar interval requirementTimes[r in Requirements] in 0..H; //tasks - one for every task
dvar interval assignmentTimes[ao in AssignmentOptions] optional in 0..H;
dvar interval travel[ao in AssignmentOptions] in 0..H;

dvar sequence taskSchedule[w in Workers] in all(ao in AssignmentOptions: ao.worker_skill.worker.worker_id == w.worker_id) assignmentTimes[ao]
	types all(ao in AssignmentOptions: ao.worker_skill.worker.worker_id == w.worker_id) ao.requirement.operation.task.id;

dexpr int nextTaskId[ao in AssignmentOptions] = (typeOfNext(taskSchedule[ao.worker_skill.worker], assignmentTimes[ao], 0));

dvar sequence fullSchedule[w in Workers] in append(
	all(ao in AssignmentOptions: ao.worker_skill.worker.worker_id == w.worker_id) assignmentTimes[ao],
	all(ao in AssignmentOptions: ao.worker_skill.worker.worker_id == w.worker_id) travel[ao]);
	

// Travel Calculation
dexpr int travelMatrix[ao in AssignmentOptions][ao2 in AssignmentOptions] = presenceOf(assignmentTimes[ao])
	* presenceOf(assignmentTimes[ao2])
	* (ao.worker_skill.worker.worker_id == ao2.worker_skill.worker.worker_id)
	* DrivingTimes[ao.requirement.operation.task.end_location][ao2.requirement.operation.task.start_location];
	
dexpr int travelTimes[ao in AssignmentOptions] = presenceOf(assignmentTimes[ao]) 
	* max(ao2 in AssignmentOptions: ao2.worker_skill.worker.worker_id == ao.worker_skill.worker.worker_id)
	(presenceOf(assignmentTimes[ao2])*(ao2.requirement.operation.task.id == nextTaskId[ao])
	* travelMatrix[ao][ao2]);

// Forward Slack Calculation
dexpr int precendentExists[ao in AssignmentOptions][ao2 in AssignmentOptions] = sum(p in Precedences)
	presenceOf(assignmentTimes[ao])
	* presenceOf(assignmentTimes[ao2])
	* (p.pre == ao2.requirement.operation.task.task)
	* (p.post == ao.requirement.operation.task.task);
	
dexpr int dependentExists[ao in AssignmentOptions][ao2 in AssignmentOptions] = sum(p in Precedences)
	presenceOf(assignmentTimes[ao])
	* presenceOf(assignmentTimes[ao2])
	* (p.pre == ao.requirement.operation.task.task)
	* (p.post == ao2.requirement.operation.task.task);
	
// End of latest precedent task (does not include travel for precendent task)
dexpr int latestPrecedent[ao in AssignmentOptions] = presenceOf(assignmentTimes[ao])
	* max(ao2 in AssignmentOptions) (precendentExists[ao][ao2]
	* (endOf(assignmentTimes[ao2])));
	
// Start of earliest dependent task
dexpr int earliestDependent[ao in AssignmentOptions] = min(ao2 in AssignmentOptions) 
	(
		(((dependentExists[ao][ao2]==1) && presenceOf(assignmentTimes[ao2]) && presenceOf(assignmentTimes[ao])) 
		* startOf(assignmentTimes[ao2]))
		
		+ (((dependentExists[ao][ao2] == 0) || !presenceOf(assignmentTimes[ao2]) || !presenceOf(assignmentTimes[ao]))
		* H)
	);

// LFT wrt fixed lft constraint, next task constraint, and precedence constraints
dexpr int lft[ao in AssignmentOptions] = presenceOf(assignmentTimes[ao])
	* (minl(minl(
		ao.requirement.operation.task.lft, 
		startOfNext(taskSchedule[ao.worker_skill.worker], assignmentTimes[ao], 0)),
		earliestDependent[ao])
	- travelTimes[ao]);
	
// Need to add if another worker has same task different skill, that also needs to move
// Need to add if another worker has 


maximize sum(r in Requirements) endOf(requirementTimes[r]);

subject to {
  forall(r in Requests) {
    span(requestTimes[r], all(rq in Requirements: rq.operation.request.request_id == r.request_id) requirementTimes[rq]);
    forall (rq in Requirements : rq.operation.request.request_id == r.request_id) {
      alternative(requirementTimes[rq], 
      	all(ao in AssignmentOptions: ao.requirement.operation.task.id == rq.operation.task.id 
      	&& ao.requirement.skill.skill_id == rq.skill.skill_id) assignmentTimes[ao]);
      sizeOf(requirementTimes[rq]) >= rq.operation.task.duration;
      // can update to compare ids here 
      forall(tc in Dependencies: tc.request == r.request && tc.task_b == rq.operation.task.task) {
        forall(rq2 in Requirements : rq2.operation.request == r && tc.task_a == rq2.operation.task.task) {
          endBeforeStart(requirementTimes[rq], requirementTimes[rq2]);
          startAtEnd(requirementTimes[rq2], requirementTimes[rq]);
        }
      }   
    }
  }
  
  forall(ao in AssignmentOptions) {
    sizeOf(travel[ao]) == travelTimes[ao];
    startAtEnd(travel[ao], assignmentTimes[ao]);
  }
  
  forall(w in Workers) {
    noOverlap(fullSchedule[w]);
    noOverlap(taskSchedule[w]);
  }
  
  forall(rq in Requirements) {
    endOf(requirementTimes[rq]) <= rq.operation.task.lft;
    startOf(requirementTimes[rq]) >= rq.operation.task.est;
  }
  
  forall(p in Precedences) {
    forall (rq in Requirements : rq.operation.request.request == p.pre) {
      forall (rq2 in Requirements: rq2.operation.request.request == p.post) {
        endBeforeStart(requirementTimes[rq], requirementTimes[rq2]);
      }
    }
  }    
};


execute {
  cp.param.FailLimit = 10000;
  var f = new IloOplOutputFile("ai_caring_updated.csv");
  f.writeln("Worker,Task,Start,End,Request,Skill");
  for(ao in AssignmentOptions) {
  	f.writeln(ao.worker_skill.worker.worker,",", 
  	ao.requirement.operation.task.task,",", 
  	assignmentTimes[ao].start,",", 
  	assignmentTimes[ao].end,",",
  	ao.requirement.operation.request.request,",",
  	ao.worker_skill.skill.skill)
  	f.writeln(ao.worker_skill.worker.worker,",", 
  	"travel,", 
  	travel[ao].start,",", 
  	travel[ao].end,",",
  	ao.requirement.operation.request.request,",",
  	"travel")
  };
  f.close()
  
   	
}
