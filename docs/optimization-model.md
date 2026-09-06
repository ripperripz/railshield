# Scheduling model and assumptions

## Time and physical abstraction

The model uses 15-minute integer slots and half-open intervals `[start,end)` relative to a timezone-aware epoch. A section represents one indivisible possession resource. Tasks each occupy one section, are non-preemptive, and require a fixed duration and fixed resource demand. The horizon is at most 31 days. Adjacent intervals may touch without conflicting.

There is no automatic rounding of imported times. An upstream adapter must conservatively round occupation starts down and ends up, and corridor starts up and ends down. Isolation, setup, restoration and safety margins must be represented as predecessor tasks or incorporated into validated windows/durations. The demo rules are illustrative; they are not a railway safety specification.

## Detailed CP-SAT formulation

For each task i, enumerate starts S_i satisfying release, deadline, one complete corridor window and every train exclusion. Let x_(i,s) be the Boolean selecting start s, and p_i = sum_s x_(i,s), with p_i=1 for required tasks. Optional tasks can defer. A task without any candidates is correctly infeasible when required.

Start_i = sum_s s*x_(i,s), End_i = Start_i + duration_i*p_i. For each predecessor j of i, p_i <= p_j and Start_i >= End_j when p_i is true. Deferred tasks do not constrain successor timing, but successors cannot execute without predecessors.

Active_(i,t) is the sum of the selected starts covering t. Section occupation Y_(section,t) is the Boolean maximum of active task expressions on that section. This computes the exact union: compatible concurrent tasks incur downtime once. Incompatible pairs have a presence-enforced before/after disjunction. Compatibility is symmetric and explicit, including any permitted same-activity pair. Missing rules mean incompatible. Pairwise checks prevent accidentally treating compatibility as transitive.

For each resource and slot, sum_i demand_(i,resource)*Active_(i,t) <= capacity_resource. Resources are global across sections. Capacity is constant over the horizon in this version. A crew-loss scenario reduces this constant; shift-specific availability is not yet modeled.

An occupation onset F_t = Y_t*(1-Y_(t-1)) counts a contiguous possession. Adjacent tasks, even sequential incompatible ones, may share one contiguous possession; overlap is only allowed for compatible work. The `shared_blocks` metric counts blocks with actual overlapping tasks, whereas total blocks counts contiguous occupation unions.

## Objective and reporting

Minimize the sum of these independently reported weighted terms:

| Term | Raw quantity | Default weight |
|---|---|---:|
| downtime | occupied section slots | 10 |
| fragmentation | occupation onsets | 5 |
| deferral | sum of priorities of deferred tasks | 10,000 |
| commitment | absolute difference between assigned week and monthly commitment | 100 |
| changed | tasks whose presence, start or end differs from parent | 1,000 |
| displacement | absolute start shift for parent tasks still scheduled | 2 |

Deferral is a weighted trade-off, not a lexicographic guarantee. Required work, deadlines, train exclusions and locks are always hard. Train interference is zero for verified plans because trains are excluded, not priced. Availability is `1 - union possession slots / (horizon slots × sections)`; it is a modeled maintenance-availability measure, not a service punctuality measure.

Results expose solver status, wall time, objective value, best lower bound and each weighted contribution. `OPTIMAL` refers only to this finite discrete model and objective. `FEASIBLE` is an incumbent without proof of optimality. `UNKNOWN` returns no assignments. CP-SAT uses one worker and a fixed seed; wall-clock limits can still cause results to vary by hardware/load.

## Baseline

The independent-planning proxy solves the identical instance with every same-section pair non-overlapping. It shares the same task/resource/window constraints and time budget. This isolates the effect of department sharing; it is not a reconstruction of historical dispatch practice or three separate department optimizers. Compare savings only when both plans are verified and schedule the same task IDs. A short solve may produce a weaker incumbent; improvement is never guaranteed or hardcoded.

## Monthly hierarchy

A separate coarse CP-SAT model assigns each task to an eligible week. Weekly section budgets sum train-free corridor slots and charge each task's full duration, conservatively ignoring sharing. Resource budgets count crew-slots across that week. Required tasks must be assigned, optional tasks may defer, and precedence requires a predecessor in the same or an earlier week.

These budgets are advisory, potentially conservative, and do not prove fine-grained feasibility. Detailed scheduling runs over the whole dataset and penalizes weekly deviations, preserving dependencies across week boundaries. A future rolling-horizon decomposition must carry completed predecessors, frozen boundary possessions and residual resource budgets explicitly; simply filtering a week's tasks is unsafe.

## Recovery and scenario semantics

A recovery lock protects presence, start and end. If a duration changes or a delayed train makes a lock impossible, return infeasibility. No automatic unlock, deletion or relaxation occurs. Newly inserted tasks count as changed. The comparison full replan deliberately removes locks and churn terms; its changed-task metric is computed against the same parent.

Stress tests retain start times, extend ends for overruns, and independently check the disrupted dataset. Scenarios cycle through supported kinds and sample targets/magnitudes from a seeded synthetic distribution. Out-of-contract perturbations are recorded invalid and excluded from the denominator. Metrics include valid sample count, observed feasibility fraction, a Wilson sample interval and violation counts. They are not empirical railway failure probabilities, financial disruption costs, or guarantees about unseen events. Maximum delay absorbed is not claimed.

## Diagnostics and limits

The independent verifier checks required work, references, durations, windows, trains, compatibility, resources, dependencies and locks before a feasible result is persisted. Infeasibility diagnostics identify zero-candidate tasks and give a general constraint checklist. They are **not** a minimal unsatisfiable core.

Not yet represented: bidirectional/multi-track partial capacity, multi-section tasks, alternative crews or equipment assignments, travel times, shift calendars, stochastic goods forecasts, task splitting, circuit-specific isolation state, train rescheduling, railway-approved route locking or dispatch authority. The domain separates activity codes and compatibility so these can be extended without coupling the API to the solver.
