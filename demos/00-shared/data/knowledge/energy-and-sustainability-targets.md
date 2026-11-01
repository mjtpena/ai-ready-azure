# Energy and sustainability targets

> **Course material, not legal or engineering advice.** Harbourline Facilities is a fictional operator and this document is a simplified summary written for the AI-Ready Azure course. Check your local building code and your own procedures before acting.

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
