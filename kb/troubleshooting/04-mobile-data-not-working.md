---
doc_type: troubleshooting
topic: mobile_data_not_working
applies_to: essential, connect, unlimited
---

# Mobile Data Not Working

A step-by-step guide for when the customer can make calls and send texts but apps and browsers do not work.

## Symptoms

- Calls and texts work, but browsing, social media, or apps do not load
- Phone shows "No Internet Connection" even with signal bars
- Apps stuck loading or display offline mode
- Data speed is extremely slow (close to zero) even with good signal

## Step 1: Confirm the customer has cellular data turned on

Sometimes the issue is as simple as a toggle:

**On iPhone:**
Settings > Cellular > Cellular Data (should be ON)

**On Android:**
Settings > Network and Internet > Internet > tap the gear next to "Cellular" > Mobile Data (should be ON)

Make sure the customer is **not connected to Wi-Fi** for this test. If they are at home on a working Wi-Fi network, the test may give misleading results.

## Step 2: Check if data is suspended due to plan limits

Use `get_customer_account` to see which plan the customer is on:

- **Essential plan** customers: high-speed data is capped at 5 GB per month. After 5 GB, speeds drop to 128 kbps for the rest of the cycle, which makes most apps unusable. Check `get_billing_info` or ask the customer if they recently received a "data limit reached" notification.

- **Connect plan** customers: high-speed data is capped at 25 GB per month. After 25 GB, speeds drop to 600 kbps. This is slow but most apps still work.

- **Unlimited plan** customers: no monthly data cap. If their data is not working, it is not because of a plan limit.

If the customer has hit their limit, explain when their cycle resets and offer plan upgrade options if they often run out.

## Step 3: Check for an account suspension

Use `get_customer_account`. If the account status is `suspended`:

- Data is disabled even though calls and texts may still work in some cases
- Explain the suspension reason (usually late payment)
- Offer to help with payment to restore service

## Step 4: Toggle airplane mode

Quick reset of the data connection:

1. Turn on Airplane mode
2. Wait 10 seconds
3. Turn off Airplane mode
4. Wait 30 seconds
5. Try opening a website that does not need login (like example.com)

If data works now, done.

## Step 5: Restart the phone

A full restart often clears stuck data connections. Power off, wait 30 seconds, power on. Test data again.

## Step 6: Check APN settings (advanced)

Most phones automatically configure the network settings for TelSano. But if the customer changed phones recently or restored from a backup of a different carrier, the APN may be wrong.

**Correct APN settings for TelSano:**

- APN: `telsano`
- APN Type: `default,supl,mms`
- MMSC: `http://mms.telsano.example.com`
- MMS Proxy: `0.0.0.0`
- MMS Port: `80`

**On iPhone**: APN cannot be edited manually. The phone uses an automatic carrier profile. If wrong, suggest resetting network settings (Settings > General > Transfer or Reset iPhone > Reset > Reset Network Settings).

**On Android**: Settings > Network and Internet > Internet > SIM > Access Point Names. Compare with the values above.

## Step 7: Reset network settings

If APN looks correct or cannot be changed, reset all network settings. Warn the customer this will erase saved Wi-Fi passwords.

**On iPhone:** Settings > General > Transfer or Reset iPhone > Reset > Reset Network Settings

**On Android:** Settings > System > Reset options > Reset Wi-Fi, mobile, and Bluetooth

After reset, the phone restarts. Test data again.

## Step 8: Try a different SIM slot or phone (advanced)

If the customer has another phone available and is comfortable swapping the SIM:

- Move the TelSano SIM to the other phone
- See if data works there

If data works on the second phone, the issue is the first phone (settings or hardware).

If data does not work on either phone, the issue is the SIM, the line, or the network.

## When to escalate

Use the `create_escalation_ticket` tool when:

- The customer is on the Unlimited plan (no data limit), has signal, is not suspended, has tried all steps above, and data still does not work
- The customer suspects their SIM is damaged or deactivated
- A SIM swap to another phone confirms the SIM is the problem

Set priority to "medium" by default. Set to "high" if the customer relies on data for work and cannot use Wi-Fi.
