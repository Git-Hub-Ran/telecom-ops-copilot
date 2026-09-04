---
doc_type: troubleshooting
topic: mobile_no_signal
applies_to: essential, connect, unlimited
---

# Mobile Signal Problems

A step-by-step guide for when a customer has no signal, weak signal, or frequent dropped calls on their mobile line.

## Symptoms

- "No service" or "Searching" displayed on the phone
- Signal bars show empty or very low
- Calls drop frequently
- Texts fail to send
- Cannot make calls even with full bars (less common)

## Step 1: Check coverage in the customer's area

Ask the customer for their current zip code (it may not be their home zip code if they are traveling).

Use the `check_network_outage` tool with that zip code. If there is an active outage:

- Apologize and confirm
- Share estimated resolution time
- Stop the diagnostic here

If there is no outage but the customer is in a known low-coverage area (rural, basement, underground parking), explain that signal can be weak in these locations and suggest:

- Moving outdoors or near a window
- Enabling Wi-Fi calling if their phone supports it

## Step 2: Toggle airplane mode

This is the fastest fix for many signal issues:

1. Turn on Airplane mode (this disconnects all wireless)
2. Wait 10 seconds
3. Turn off Airplane mode
4. Wait 30 seconds for the phone to find the network
5. Check the signal

If the signal is back, the issue was a stuck connection to a tower. Done.

If the signal is still missing, continue to Step 3.

## Step 3: Restart the phone

A full restart often fixes signal issues that airplane mode does not:

1. Power off the phone completely (not just lock screen)
2. Wait 30 seconds
3. Power on
4. Wait for the phone to fully boot and connect to the network

Check signal. If restored, done. If not, continue.

## Step 4: Check the SIM card

For physical SIM cards:

1. Power off the phone
2. Open the SIM tray (a paper clip or SIM tool is needed)
3. Remove the SIM card
4. Wait 30 seconds
5. Re-insert the SIM card firmly
6. Close the tray
7. Power on the phone

For eSIM (no physical card):

- Ask the customer to check Settings > Cellular and confirm their TelSano line is active
- If the line is missing, the eSIM may have been removed and needs to be reactivated. Escalate.

## Step 5: Check the customer's account

Use `get_customer_account` to verify:

- Is the line **active** (not suspended for late payment)?
- Is the line on a **valid plan**?
- Was the line recently changed or transferred? Changes can take up to 4 hours to fully activate.

If the line is suspended due to late payment, refer to the late fees policy and offer to help process payment.

## Step 6: Reset network settings

If everything else fails, resetting network settings often helps. Warn the customer this will erase saved Wi-Fi passwords:

**On iPhone:**
Settings > General > Transfer or Reset iPhone > Reset > Reset Network Settings

**On Android:**
Settings > System > Reset options > Reset Wi-Fi, mobile, and Bluetooth

The phone restarts and the issue is often resolved.

## International or roaming considerations

If the customer is traveling outside the US:

- Essential plan: international roaming is **not included**. The customer needs to add an international pass.
- Connect plan: includes Canada and Mexico calls and texts, but data may need an add-on.
- Unlimited plan: includes Canada and Mexico calls, texts, and data at reduced speed. Other countries need an add-on.

Refer the customer to international add-on options if they are traveling.

## When to escalate

Use the `create_escalation_ticket` tool when:

- All steps above have been tried and the signal is still missing
- Multiple customers in the same area report the same issue (suggests tower problem not yet flagged)
- The customer believes their SIM card or eSIM may be damaged or deactivated

Set priority to "medium" for one customer. Set to "high" if multiple customers report the same area.
