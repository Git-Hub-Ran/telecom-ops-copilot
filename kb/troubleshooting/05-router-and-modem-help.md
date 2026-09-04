---
doc_type: troubleshooting
topic: router_and_modem_help
applies_to: internet_100, fiber_1000
---

# Router and Modem Help

A guide for understanding equipment indicator lights, the difference between reset and restart, and common equipment issues.

## What the lights mean

The TelSano Wi-Fi 6 router (included free with Fiber 1000) and the standard modem use color and pattern to show status. Read the lights from top to bottom.

### Power light

- **Solid green or white**: device has power and is working
- **Off**: no power. Check the power cable and wall outlet
- **Solid red**: device is in error state. Try a power cycle. If still red, escalate for replacement.

### Internet or WAN light (router only)

- **Solid green or white**: connected to the internet
- **Blinking**: data is flowing (this is normal during use)
- **Off**: not connected. Check the cable between the modem and router.
- **Red**: connection failed. Power cycle both modem and router.

### Wi-Fi light (router only)

- **Solid or blinking green / white**: Wi-Fi is on and broadcasting
- **Off**: Wi-Fi is turned off. Press the Wi-Fi button on the back of the router for 2 seconds to enable it.

### Cable / DSL / Fiber light (modem only)

- **Solid green or white**: connected to the TelSano network
- **Blinking**: trying to connect (this can last up to 5 minutes after a restart)
- **Off**: no signal from TelSano. Check the cable from the wall. If the cable is firmly attached and the light is still off, there may be a line issue. Escalate.
- **Red**: signal is detected but failed authentication. Power cycle and wait 5 minutes. If still red, escalate.

## Restart vs reset (these are very different)

A common source of confusion. Customers often say "reset" when they mean "restart." It matters which one they actually do.

### Restart (also called "power cycle")

This is the **safe option** and the first thing to try.

1. Unplug the device from power
2. Wait 60 seconds
3. Plug it back in
4. Wait for lights to become solid

A restart does not change any settings. The Wi-Fi name, password, and configuration are kept.

### Factory reset

This is the **drastic option** and should be used only if a TelSano agent or support article specifically says to.

A factory reset erases:

- Custom Wi-Fi network name and password (returns to default printed on the back of the router)
- Saved devices and parental controls
- Any custom port forwarding or network rules

To factory reset most TelSano routers:

1. Find the small reset button on the back of the router (usually a tiny hole)
2. Insert a paper clip and **hold for 10 seconds**
3. Release when all lights start blinking
4. Wait 3 to 5 minutes for the router to fully restart

After a factory reset, the customer needs to reconnect all devices using the default Wi-Fi password (printed on the back of the router).

If the customer accidentally did a factory reset, this is normal and recoverable. Just walk them through reconnecting their devices.

## Common equipment problems

### "I want to change my Wi-Fi password"

The customer can change it in two ways:

1. Through the TelSano mobile app: "Network" > "Wi-Fi Settings"
2. By going to 192.168.1.1 in a web browser while connected to the router. The default admin password is on the back of the router.

The new password takes effect immediately. Devices will need to reconnect with the new password.

### "My router gets very hot"

A slightly warm router is normal. A router that is hot to the touch all over is usually:

- Blocked airflow (in a closed cabinet, under a stack of books)
- Failing internal fan

Suggest moving the router to an open shelf with airflow. If still hot after 24 hours, escalate for replacement.

### "My router keeps disconnecting"

This is usually one of:

- Overheating (see above)
- Power supply failure: try using a different power outlet. If the router stays on at one outlet but not another, the outlet may have a loose connection. If it disconnects at all outlets, the router or its power adapter is failing.
- Firmware issue: TelSano routers update automatically. Force an update by pressing the reset button for 2 seconds (not 10, which is a factory reset).

### "I want to use my own router instead of yours"

Internet 100 customers can bring their own router from day one. Fiber 1000 customers can do this too, but they must continue to keep the TelSano router (it stays the property of TelSano even when unused).

Tell the customer:

- They are responsible for configuring their own router
- TelSano support can help with basic setup but cannot deeply troubleshoot non-TelSano equipment
- If they cancel service, the TelSano router must still be returned even if it was never used

## When to escalate

Use the `create_escalation_ticket` tool when:

- A router or modem light is consistently red after a power cycle
- A factory reset did not solve a recurring issue
- The customer reports physical damage to the equipment (cracks, burned smell, water exposure)
- The same equipment problem returns repeatedly after each fix

In most equipment escalations, TelSano ships a replacement within 2 business days. The customer returns the old device using a prepaid label.
