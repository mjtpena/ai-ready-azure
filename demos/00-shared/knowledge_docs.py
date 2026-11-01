"""Grounding documents for the Site Operations Advisor demo.

Eight short, simplified internal-guidance style documents for Harbourline Facilities, a fictional smart-building
operator. They are written for the course, deliberately simplified, and are NOT legal, engineering or compliance
advice. ``generate_data.py`` writes them to ``data/knowledge/`` so they can be chunked (one chunk per ``##`` section),
embedded and indexed. The standards bodies named here (the Vertical Transport Safety Register, the Fire Systems
Compliance Schedule) are fictional.
"""

DISCLAIMER = (
    "> **Course material, not legal or engineering advice.** Harbourline Facilities is a fictional operator and this "
    "document is a simplified summary written for the AI-Ready Azure course. Check your local building code and your own "
    "procedures before acting."
)

KNOWLEDGE_DOCS: dict[str, str] = {
    "hvac-fault-response-sop.md": f"""
# HVAC fault response SOP

{DISCLAIMER}

## Scope and first response

This procedure covers chillers, air handling units (AHUs), variable air volume boxes and the building management
system (BMS) alarms they raise. Every HVAC alarm that the BMS classifies as a fault creates a work order
automatically. The site operations desk acknowledges the alarm within 15 minutes, checks the asset history in the
BMS, and decides whether the fault needs a contractor or can be cleared remotely (a single nuisance trip with no
repeat and no tenant impact can be reset once from the BMS).

## Chiller trips

A chiller trip is a fault where the chiller shuts itself down on a protection limit such as high condenser pressure,
low refrigerant pressure or a flow failure. One trip may be reset once from the BMS after the cause has been checked.
**If a chiller trips twice in the same day, the site operations desk locks the chiller out: do not attempt a third
reset.** Call the mechanical contractor and have them attend within 2 hours. Raise the work order to P1 when the site
is a medical centre or an office tower during business hours, otherwise keep it at P2. Notify the site manager in both
cases and record the lockout in the work order.

## Zone temperature and air handling faults

The comfort target for occupied office space is 22 to 24 degrees Celsius. A zone above 26 degrees for 60 minutes
during occupied hours is a P2 fault: check the AHU supply air temperature and the chilled water valve position before
calling the contractor. A supply fan VSD fault takes the AHU out of service; move the affected floors onto the
neighbouring AHU where the BMS allows it and raise a P2 work order for the contractor.

## Refrigerant leaks

A low refrigerant pressure alarm is treated as a suspected leak. Isolate the circuit, ventilate the plant room, keep
people out of the plant room until the contractor has tested the space, and raise a P2 work order. Leaks are reported
in the monthly sustainability report because refrigerant loss counts against the site's emissions target.

## Faults open longer than 48 hours

Any HVAC work order that is still open after 48 hours is escalated to the regional facilities manager the same day.
The contractor must provide a written recovery plan with a date, and the site manager decides whether temporary
cooling or tenant communication is needed. Do not carry out a fire-system inspection on a floor that has an active
HVAC fault until the fault owner has confirmed the floor is safe to work on.
""",
    "lift-incident-and-entrapment-procedure.md": f"""
# Lift incident and entrapment procedure

{DISCLAIMER}

## Incident types

Lift incidents recorded by the lift controllers are classified as entrapment (a person is in a stopped car between
floors or behind closed doors), door fault (doors fail to close or cycle repeatedly), levelling fault (the car stops
more than 20 millimetres from floor level) and out of service (the controller has taken the lift out of service on a
fault). Entrapments are always P1; out of service is P2; door and levelling faults are P3 unless they repeat.

## Entrapment response

An entrapment is a P1 incident. The site operations desk establishes voice contact with the trapped person through
the car intercom within 2 minutes and stays in contact until release. The lift contractor must attend within 30
minutes; the desk calls the emergency services if anyone in the car is unwell or distressed, or if the contractor
cannot meet the 30-minute target. **Harbourline staff never attempt to release a trapped person themselves**: only
the lift contractor or the emergency services open a stalled car.

## Reporting entrapments

Every entrapment is reported to the Vertical Transport Safety Register within 24 hours using the register's incident
form, with the lift id, the duration of the entrapment and the contractor's findings. The site manager also sends a
tenant notice the same day. Entrapments are reviewed at the monthly operations meeting.

## Repeat door faults and out-of-service lifts

Three door faults on the same lift within a week trigger a contractor inspection of the door operator, even when each
fault cleared on its own. A lift that is out of service gets out-of-service signage on every landing within 30 minutes
and a tenant notice if it will be out for more than 4 hours. Where a building has a single lift, an out-of-service
lift is raised to P1 because it removes accessible access to the upper floors.
""",
    "fire-system-inspection-schedule.md": f"""
# Fire system inspection schedule

{DISCLAIMER}

## Inspection cycle

Every site follows three cycles under the Fire Systems Compliance Schedule issued under the local building code: a
**monthly test** of the detection and alarm system carried out by the fire contractor, an **annual certificate**
inspection carried out by an approved inspector, and a **five-yearly sprinkler test** of the sprinkler system where
one is installed. The monthly test is logged in the BMS as a fire_test event; a failed test raises a P2 work order.

## What "due this month" means

A certificate inspection (the annual certificate or the five-yearly sprinkler test) is due this month when its next
due date falls inside the current calendar month, whether or not the date has passed. The inspection schedule tool
lists the certificate inspections due in a month, everything already overdue, and the routine monthly tests
separately, because an overdue certificate carries the heavier consequences below while a monthly test is routine
contractor work.

## Certificates that are expiring or overdue

A certificate is expiring when it falls due within the next 30 days: book the inspector at least 2 weeks ahead so the
inspection happens before the due date. A certificate that is past its due date is overdue: the site manager escalates
to the regional facilities manager the same day, no hot-work permits are issued at that site until the certificate is
renewed, and the insurer is told if the overdue period passes 14 days.

## Who may inspect

Monthly tests are carried out by the site's fire contractor. Annual certificates and five-yearly sprinkler tests must
be carried out by an inspector approved under the compliance schedule; the site's own fire contractor may hold that
approval, but the operations desk checks the inspector firm on the schedule before booking.

## Reducing false alarms

False alarms are reviewed monthly by site. The common causes are detector dust in plant rooms, contractor hot work
without an isolation, and cooking in tenancy kitchens. The responses are, in order: clean or relocate the detector,
require a fire-system isolation on every hot-work permit, and fit a heat detector in place of a smoke detector in
kitchens where the code allows it. A site with more than three false alarms in a month gets a detector survey.
""",
    "work-order-priorities-and-sla.md": f"""
# Work order priorities and SLAs

{DISCLAIMER}

## Priority levels

Work orders carry one of three priorities. **P1** is a safety or business-critical fault: an entrapment, a fire-system
fault that disables detection, a chiller lockout at a medical or office site in business hours, or a single-lift
building with its lift out. **P2** is a fault with tenant impact but no immediate safety risk, for example an AHU out
of service or a false-alarm investigation. **P3** is planned or minor work: a door that reopens occasionally, a forced
loading-dock door with no loss, or a preventive maintenance visit.

## SLA hours

The contractor response SLA is measured from the time the work order opens to the time the fault is cleared or made
safe: **P1 within 4 hours, P2 within 24 hours, P3 within 72 hours.** A work order whose age passes its SLA hours is
breached, and the breach is recorded against the contractor at the monthly contractor review.

## HVAC work open longer than 48 hours

Any HVAC work order open longer than 48 hours is reviewed by the regional facilities manager, who asks the contractor
for a written recovery plan with a date and decides with the site manager whether temporary cooling or a tenant notice
is needed. This review is separate from the SLA: a P3 HVAC work order is inside its 72-hour SLA at 48 hours and is still
reviewed.

## Weekly open work order review

Every Monday the regional facilities manager reviews all open work orders for the region: anything past its SLA,
anything open longer than 48 hours, and any site with more than three open work orders. Sites with repeat faults on the
same asset are flagged for a condition assessment.

## Closing a work order

A work order is closed when the contractor has recorded the cause, the fix and the parts used, and the BMS shows the
alarm cleared. Work orders closed without a cause are reopened by the operations desk.
""",
    "contractor-safety-and-access.md": f"""
# Contractor safety and site access

{DISCLAIMER}

## Induction and sign-in

Every contractor working at a Harbourline site holds a current site induction, renewed yearly, and signs in at the
access control reader or the building app before starting work. The access control system records each sign-in as a
contractor_sign_in event against the work order the contractor is attending. A contractor who has not signed in is
asked to leave the plant areas until they have.

## Permit to work

Hot work, work at height, work on the fire system and any isolation of a life-safety system need a permit to work
issued by the site manager before the work starts. A hot-work permit requires a fire-system isolation and a fire watch
for 60 minutes after the work ends; no hot-work permit is issued at a site whose fire certificate is overdue.

## After-hours access

Contractor access outside 07:00 to 18:00 local time requires an approved after-hours permit and a named Harbourline
site contact who can be reached by phone for the whole visit. **A contractor may not work on site after hours without
a permit on file.** After-hours access without a permit is logged as a warning and reviewed by the site manager the
next working day.

## Forced doors and badge bursts

A forced door alarm (loading dock, plant room or fire stair) raises a P3 work order for the field team to inspect the
door and the camera footage. A burst of denied badge reads at one reader (five or more in two minutes) is usually a
contractor using an expired badge; the operations desk confirms the person on camera and reissues the badge or
escalates to security.
""",
    "energy-and-sustainability-targets.md": f"""
# Energy and sustainability targets

{DISCLAIMER}

## Baselines

Each site has a daily energy baseline in kilowatt-hours, calculated from the previous twelve months of smart meter
readings for the same weekday type (weekday or weekend) and adjusted for net lettable area. The baseline is recorded
with every daily consumption reading so a site's performance can be read without a separate lookup.

## What counts as an anomaly

A day's consumption more than 20 per cent above its baseline is an energy anomaly. The BMS raises an energy_anomaly
event, and the regional facilities manager reviews it within two working days and decides the corrective action. The
usual causes are a chiller running
in a fault state, an AHU left in manual after contractor work, or lighting and plant left on after hours.

## After-hours load

The after-hours target is that a site uses no more than 35 per cent of its daytime load between 20:00 and 06:00. Sites
above the target for a week are checked for plant schedules left in override.

## Monthly reporting

The sustainability report published each month lists consumption against baseline by site and region, the number of
anomaly days, refrigerant losses reported through HVAC work orders, and progress against the portfolio's emissions
target. Numbers in the report come from the smart meter readings and the work order system, not from estimates.
""",
    "site-operations-platform-overview.md": f"""
# Site operations platform: reference architecture overview

{DISCLAIMER}

## From sensors to context

Building telemetry starts at the edge: BMS controllers, lift controllers, fire indicator panels, access control
readers and smart meters publish events to an ingestion tier. Stream processing validates and enriches each event with
the site and asset it belongs to, then lands it in two places: a lakehouse for history and a real-time store for the
last few days. Work orders, inspections and SOP documents sit beside the telemetry as the operations context.

## The Site APIs and the advisor's tools

The platform exposes the operations context as Site APIs. The Site Operations Advisor agent reaches them as four
tools: get_site_summary for one site, get_open_work_orders for work open longer than a number of hours, get_incidents
for incidents over a window of days, and get_inspection_schedule for statutory inspections due in a month. Every figure
the advisor states comes from one of these tools; it never reads raw telemetry itself. The tools are published through
the organisation's AI gateway so the same identity, budget and logging rules apply to agents as to applications.

## The knowledge index

Procedures such as this document are chunked by section, embedded and indexed in Azure AI Search. The advisor searches
that index for rules and guidance and cites the document titles it used. Figures come from tools, rules come from the
index.

## Identity, gateway, observability and evaluation

Every call the advisor makes carries an identity: the agent has its own Entra identity, the tools are reached through
one gateway with token and request budgets, every step is traced with OpenTelemetry into Application Insights, and
each new version of the advisor passes an evaluation gate before it is published. The five platform layers are
foundation, trust and control, data and context, intelligence, and experiences and agents.
""",
    "tenant-communications-and-scope.md": f"""
# Tenant communications and the scope of operations guidance

{DISCLAIMER}

## What the operations team advises on

The site operations team and the Site Operations Advisor give guidance on building systems and services: HVAC, lifts,
fire systems, access control, energy, work orders, inspections and contractor management. The advisor can summarise a
site or a region from telemetry and explain the procedures in these documents.

## What goes to the leasing and legal team

**Rent, lease terms, lease termination, evictions, tenant disputes and anything else about the commercial or legal
relationship with a tenant are outside the scope of operations guidance.** These questions go to the leasing and legal
team, and the operations team does not give an opinion on them, even informally. The advisor declines such questions
and says who handles them.

## Tenant notices

The operations team sends tenant notices for planned outages, lifts out of service for more than 4 hours, HVAC faults
expected to last more than a working day, and fire-system tests that will sound alarms. Notices use the standard
template: what is affected, from when to when, what tenants should do, and who to contact. Notices are sent by the
site manager, and a copy is attached to the work order.

## Complaints and comfort

Comfort complaints (too hot, too cold, lift waiting times) are logged as service requests and checked against the
BMS data before a contractor is called. The operations team replies within one working day with what was found and
what will change.
""",
}
