# Pilot intake questionnaire

## 1. Workload identity

- Workload name:
- Owner/team:
- Business purpose:
- Frequency: hourly / daily / per training run / per query / other:

## 2. What is a slot?

Examples: GPU, host, storage node, worker, partition, network endpoint, disk, bucket, rack.

- Slot definition:
- Number of slots:
- Are all slots equivalent? yes/no
- If not equivalent, describe classes:

## 3. Transfer demands

Can you provide a CSV with:

```csv
src_slot,dst_slot,bits_total
0,1,65536
```

- Is direction important? yes/no
- Are duplicate pairs expected? yes/no
- Typical total data volume:
- Typical number of pairs:

## 4. Capacity assumption

- How much can one active transfer move per tick/window?
- What is the time meaning of one tick/window?
- Can a slot send and receive in the same tick? yes/no
- Can a slot participate in multiple transfers in the same tick? yes/no
- Is broadcast/fanout allowed? yes/no

## 5. Existing schedule

- Do you already have a schedule/log of actual transfers? yes/no
- Format:
- Can we compare against it? yes/no

## 6. Cost model

- Cost per GPU-hour:
- Cost per node-hour:
- SLA/latency cost:
- Transfer egress cost:
- Preferred cost unit:

## 7. Security and data handling

- Can metadata leave your environment? yes/no
- Is on-prem execution required? yes/no
- Are slot IDs sensitive? yes/no
- Do we need anonymization? yes/no

## 8. Success criteria

What would make the pilot valuable?

- Find conflicts
- Reduce ticks
- Improve utilization
- Establish CI gate
- Explain bottleneck
- Compare schedulers
- Other:
