---
doc_type: troubleshooting
topic: no_internet_connection
applies_to: internet_100, fiber_1000
---

# No Internet Connection

A step-by-step guide for when a customer has no internet at home at all.

## Symptoms

- All devices show "no internet" or "limited connectivity"
- Web pages do not load on any device
- Wi-Fi network is visible but cannot connect, OR Wi-Fi network is missing
- Lights on the router or modem look wrong (off, red, or only some on)

## Step 1: Check for a network outage

Before any other steps, use the `check_network_outage` tool with the customer's zip code.

If there is an outage:

- Apologize and confirm the outage in their area
- Share the estimated resolution time
- Mention that an automatic credit will be applied if the outage lasts more than 24 hours
- Stop the diagnostic here

If there is no outage in the area, continue to Step 2.

## Step 2: Check the equipment lights

Ask the customer to look at the lights on their modem and router. The expected light patterns are:

### Modem (the box connected to the wall)

- **Power**: solid green or white
- **Cable / DSL / Fiber** (depending on technology): solid green or white
- **Internet**: solid green or white

### Router (the box that broadcasts Wi-Fi)

- **Power**: solid green or white
- **Internet** (or "WAN"): solid green or white
- **Wi-Fi**: solid green or white (or blinking is okay, that means activity)

If any light is **off, red, or amber**, that points to the source of the problem.

## Step 3: Power cycle the equipment

This fixes most no-connection issues:

1. Unplug the modem and the router from power
2. Wait **60 seconds**
3. Plug the modem back in first
4. Wait until the modem lights are solid (1 to 2 minutes)
5. Plug the router back in
6. Wait until the router lights are solid (2 to 3 minutes)
7. Try to connect again

If the connection is back, the issue was a stuck connection. Done.

If the connection is still down, continue to Step 4.

## Step 4: Check physical cables

Ask the customer to:

1. Confirm the power cable on the modem is fully plugged in at both ends
2. Confirm the cable from the wall (coaxial, phone line, or fiber) is screwed in or clicked in fully
3. Confirm the network cable from the modem to the router is firmly seated at both ends

Loose cables are a common cause, especially after cleaning, moving furniture, or pets bumping equipment.

## Step 5: Try a different device

Ask the customer to try connecting with a different device (phone, laptop, tablet). If only one device cannot connect, the problem is with that device, not the internet.

If no device can connect, the issue is with the internet or equipment.

## Step 6: Look up the customer's account

Use `get_customer_account` to check:

- Is the account **active** (not suspended for late payment)?
- Is the home internet service **enabled** (not paused or canceled)?

If the account is suspended, see the late fees policy and offer to help the customer make a payment to restore service.

## When to escalate

Use the `create_escalation_ticket` tool when:

- All steps above have been tried and the connection is still down
- The modem or router lights show a hardware failure (consistent red light or no power)
- The customer reports the issue started after recent maintenance (suggests a line cut)

Set priority to "high" if the customer is unable to work from home or has no other internet options. Most no-connection escalations result in a technician visit within 24 hours.
