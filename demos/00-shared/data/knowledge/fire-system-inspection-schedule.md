# Fire system inspection schedule

> **Course material, not legal or engineering advice.** Harbourline Facilities is a fictional operator and this document is a simplified summary written for the AI-Ready Azure course. Check your local building code and your own procedures before acting.

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
