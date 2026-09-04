---
doc_type: troubleshooting
topic: slow_internet
applies_to: internet_100, fiber_1000
---

# Slow Internet Speed

A step-by-step guide for diagnosing slow internet speed on home internet plans.

## Symptoms

- Web pages load slowly
- Video streaming buffers often or drops to low quality
- Speed test results are much lower than the plan's advertised speed
- Video calls freeze or disconnect

## Step 1: Run a speed test

Ask the customer to run a speed test from a device **connected directly to the router with a network cable** (not Wi-Fi):

1. Open a web browser
2. Go to speedtest.net or fast.com
3. Wait for the test to complete and note the download and upload numbers

Expected results:

- **Internet 100** plan: 90 to 110 Mbps download, 18 to 22 Mbps upload
- **Fiber 1000** plan: 900 to 1000 Mbps download and upload

If the wired speed is close to expected, the problem is likely with Wi-Fi or a specific device. Move to Step 4.

If the wired speed is much lower than expected, continue to Step 2.

## Step 2: Power cycle the router and modem

This solves most speed issues by clearing the device's memory and re-establishing the connection:

1. Unplug both the router and the modem from power (some customers have a combined unit)
2. Wait **60 seconds**
3. Plug the modem back in first
4. Wait for the modem's lights to become solid (not blinking), usually 1 to 2 minutes
5. Plug the router back in
6. Wait for the router lights to become solid, usually 2 to 3 minutes
7. Run another speed test

If the speed is now normal, the issue was a stuck connection. No further action needed.

If the speed is still slow, continue to Step 3.

## Step 3: Check for a network outage

Use the `check_network_outage` tool with the customer's zip code. If there is an active outage:

- Apologize and confirm the outage
- Share the estimated resolution time
- Mention that an automatic credit will be applied if the outage lasts more than 24 hours

If there is no outage, continue to Step 4.

## Step 4: Check Wi-Fi specific issues

Slow Wi-Fi (but fast wired) is usually one of these:

- **Distance from router**: ask if the customer is in the same room as the router. Try moving closer.
- **Too many devices**: ask how many devices are connected. More than 15 active devices on Internet 100 can slow things down.
- **Old device**: phones or laptops older than 5 years may not support modern Wi-Fi speeds.
- **Wi-Fi channel congestion**: common in apartment buildings. Suggest changing the Wi-Fi channel in router settings.

## Step 5: Time of day patterns

Ask if the slowness happens only at certain times. Internet usage peaks between 7 PM and 11 PM in most areas. If the slowness is only during these hours, this is normal congestion, and a service upgrade may help.

## When to escalate

Use the `create_escalation_ticket` tool when:

- The wired speed test is less than 50% of the expected plan speed and a power cycle did not help
- The customer reports the issue has persisted for more than 2 days
- The customer has already tried these steps before

Set priority to "medium" for first-time complaints, "high" if the customer has called multiple times.
