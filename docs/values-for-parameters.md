# Bafang Controller Parameter Values Guide

This guide explains how to interpret and set parameter values in the JSON configuration file.

## File Structure

```json
{
  "general": { ... },      // Read-only controller info, do not change!
  "basic": { ... },        // Motor assistance parameters
  "pedal_assist": { ... }, // Pedal sensor parameters
  "throttle": { ... }      // Throttle handle parameters
}
```

## General Block

**Read-only information about your controller.** These values are displayed for reference but cannot be changed.

```json
"general": {
  "manufacturer": "SZBF",
  "model": "SW09",
  "hardware_version": "V2.0",
  "firmware_version": "V1.0.0.4",
  "nominal_voltage_code": 2,
  "nominal_voltage_str": "48V",
  "cut_off_voltage_min": 38,
  "cut_off_voltage_max": 43,
  "max_current_amps": 18
}
```

| Parameter | Meaning |
|-----------|---------|
| `nominal_voltage_code` | 0=24V, 1=36V, **2=48V**, 3=60V, 4=24-48V, 5=24-60V |
| `cut_off_voltage_min/max` | Battery voltage range in V. (user cannot change) |
| `max_current_amps` | Hardware current limit in A. (user cannot change) |

---

## Basic Parameters (BAS)

Core motor assistance and speed limiting configuration.

### `low_battery_protect`

**Allowed:** 18-55 V (depends on your voltage system)

The battery voltage at which the motor stops assisting to protect the battery from over-discharge.

```json
"low_battery_protect": 38
```

- **48V system:** typically 38-43V
- **36V system:** typically 28-32V
- **24V system:** typically 18-22V

**Example:** 38V means "stop assist when battery drops below 38V"

### `current_limit_amps`

**Allowed:** 0-255 A (limited by your controller hardware)

The maximum current the motor can draw from the battery.

```json
"current_limit_amps": 15
```

- **15A** = moderate speed, good efficiency
- **18A** = maximum (hardware limit)
- **10A** = lighter assistance, longer range
- **0A** = motor disabled

**Note:** Cannot exceed your controller's hardware limit (typically 18A for this controller).

### `assist_current_limits` (array of 10 values)

**Allowed:** 0-255 (as % of motor capability)

Motor current for each assist level (0=weakest, 9=strongest).

```json
"assist_current_limits": [0, 11, 22, 33, 44, 55, 66, 77, 88, 100]
```

Each level controls how hard the motor works:

| Level | Example % | Typical Use |
|-------|-----------|------------|
| 0 | 0% | No assist (coasting) |
| 1 | 11% | Very light assist, high efficiency |
| 2 | 22% | Light assist, good range |
| 3 | 33% | Moderate assist |
| 4 | 44% | Moderate-strong assist |
| 5 | 55% | Good climbing assist |
| 6 | 66% | Strong assist |
| 7 | 77% | Very strong assist |
| 8 | 88% | Maximum assist (high power) |
| 9 | 100% | Full motor power |

**Example:** Setting level 5 to `55` means "in assist level 5, the motor provides 55% of its maximum current"

### `assist_speed_limits` (array of 10 values)

**Allowed:** 0-100 (as % of motor maximum speed)

Speed limit for each assist level. The reference maximum is **31 km/h** for the SW09 at 48V.

```json
"assist_speed_limits": [0, 90, 90, 90, 90, 90, 90, 90, 90, 90]
```

**Formula:** `Actual Speed = (value ÷ 100) × 31 km/h`

| Value | Resulting Speed | EU Legal? | Use Case |
|-------|-----------------|-----------|----------|
| 0 | 0 km/h | - | Disabled |
| 50 | ~15.5 km/h | ✓ Yes | Low-speed pedaling |
| 80 | ~24.8 km/h | ✓ Yes | Near EU limit (25 km/h) |
| 90 | ~28 km/h | ✓ Borderline | Higher speed assistance |
| 100 | ~31 km/h | ✗ No | Full motor speed (illegal in EU) |

**Example:** Your current setting of `90` on all levels = **28 km/h maximum** (close to EU legal limit of 25 km/h).

### `wheel_diameter_code`

**Allowed:** 31-60

Code representing your wheel size. This affects speed calculation from motor RPM.

```json
"wheel_diameter_code": 56  // 28 inch wheel
```

**Wheel Diameter Mappings:**

| Code | Size | Code | Size |
|------|------|------|------|
| 31-32 | 16 inch | 47-48 | 24 inch |
| 33-34 | 17 inch | 49-50 | 25 inch |
| 35-36 | 18 inch | 51-52 | 26 inch |
| 37-38 | 19 inch | 53-54 | 27 inch |
| 39-40 | 20 inch | **55** | **700C** |
| 41-42 | 21 inch | 56 | 28 inch |
| 43-44 | 22 inch | 57-58 | 29 inch |
| 45-46 | 23 inch | 59-60 | 30 inch |

**Importance:** This value is **critical** for accurate speed readings. Set it to match your actual wheel size.

**Example:** Code 56 = 28-inch wheel. If you use a 26-inch wheel (code 51), speed will be miscalculated.

### `speed_meter_type`

**Allowed:** 0, 1, 3

How the speed sensor measures rotation:

```json
"speed_meter_type": 0
```

| Value | Type | Meaning |
|-------|------|---------|
| **0** | External, Wheel Meter | Sensor on wheel rim (most common) |
| **1** | Internal, Motor Meter | Sensor inside motor |
| **3** | By Motor Phase | Derived from motor windings |

**Note:** Always verify which type matches your setup. Wrong type = wrong speed readings.

### `speed_meter_signals`

**Allowed:** 1-63

Number of sensor signals per speed-meter or wheel rotation.

```json
"speed_meter_signals": 1
```

- **1** = one magnet on wheel rim (standard)
- **2-8** = multiple magnets for higher resolution
- Higher numbers = more accurate speed but require more sensor points

---

## Pedal Assist Parameters (PAS)

Configuration for pedal-assist mode (cadence-based assistance).

### `pedal_sensor_type`

**Allowed:** 0, 1, 2, 3

Type of pedal sensor attached:

```json
"pedal_sensor_type": 3
```

| Value | Type | Signals |
|-------|------|---------|
| 0 | None | No pedal sensor (PAS disabled) |
| 1 | DH-Sensor-12 | 12 signals per rotation |
| 2 | BB-Sensor-32 | 32 signals per rotation |
| **3** | DoubleSignal-24 | 24 signals per rotation |

**Example:** Type 3 detects every 15° of crank rotation (360° ÷ 24).

### `designated_assist`

**Allowed:** 0-9, or **255** (By Display)

Which assist level to use automatically:

```json
"designated_assist": 255
```

- **255** = "By Display" - use LCD/display's selected level
- **0-9** = fixed level (locked to that level regardless of display)

**Example:** Setting to `5` forces level 5 assist; setting to `255` lets the rider choose via display.

### `speed_limit`

**Allowed:** 0-27, or **255** (By Display)

Speed limit in km/h specifically for PAS mode:

```json
"speed_limit": 255
```

- **255** = "By Display" - use the speed limit from BAS block
- **0-27** = fixed km/h limit (15-27 typical)

**Example:** Setting to `25` limits PAS assistance to 25 km/h, regardless of BAS setting.

### `start_current_pct`

**Allowed:** 1-20 (%)

Motor current when you first start pedaling:

```json
"start_current_pct": 10
```

- **1-5%** = gentle, smooth start
- **10%** = normal responsive start
- **15-20%** = aggressive immediate torque

**Use Case:** Low value for comfort, high value for climbing assistance.

### `slow_start_mode`

**Allowed:** 1-8

How quickly assistance ramps up from start:

```json
"slow_start_mode": 4
```

| Value | Ramp Speed | Feel |
|-------|-----------|------|
| 1 | Very slow | Gradual, smooth power delivery |
| 4 | Moderate | Balanced (typical) |
| 8 | Instant | Immediate full power |

**Example:** Value 1 feels "soft and smooth"; value 8 feels "direct and responsive".

### `start_degree`

**Allowed:** 1-100 (degrees of crank rotation)

How far you must turn the crank before assistance engages:

```json
"start_degree": 4
```

- **1-5°** = Very responsive, assist begins almost immediately
- **10-20°** = Standard, slight delay before assist kicks in
- **30-100°** = Noticeable delay (rare, for very gentle assist)

**Example:** Setting to `4°` means "after 4° of pedal turn, motor engages".

### `work_mode`

**Allowed:** 10-80 (RPM), or **255** (Undetermined/Cadence)

Motor output mode:

```json
"work_mode": 255
```

- **255** = Cadence-based (maintain target RPM)
- **10-80** = Fixed RPM mode (rare, not typically used)

**Example:** Value 255 means "assist in cadence mode, adapting to your pedaling speed".

### `stop_delay`

**Allowed:** 0-255 (in 100ms units)

Time motor continues after you stop pedaling:

```json
"stop_delay": 25  // 25 × 100ms = 2.5 seconds
```

- **0** = Stop immediately when pedaling stops
- **25** = 2.5 seconds of coasting assist
- **255** = 25.5 seconds of coasting assist

**Example:** Setting to `25` lets motor coast for 2.5 seconds after pedal stops, smoothing the cutoff.

### `current_decay`

**Allowed:** 0-255

How power fades out during pedaling:

```json
"current_decay": 8
```

- **0** = No decay (hard cutoff)
- **1-8** = Gradual fade
- **255** = Very gradual fade

### `stop_decay`

**Allowed:** 0-255 (in 100ms units)

Time to gradually fade assistance after stopping:

```json
"stop_decay": 0  // 0 × 100ms = immediate cutoff
```

- **0** = Immediate cutoff
- **5-20** = Smooth fade to stop

### `keep_current_pct`

**Allowed:** 0-255 (%)

Percentage of assistance to maintain during coasting:

```json
"keep_current_pct": 80
```

- **0%** = No assistance during coasting
- **50%** = Half assistance while coasting
- **80-100%** = Nearly full assistance while coasting

---

## Throttle Parameters (THR)

Configuration for throttle handle (twist-grip) assistance.

### `start_voltage`

**Allowed:** 0-255 (in 0.1V units)

Voltage at which throttle begins to engage:

```json
"start_voltage": 11  // 11 × 0.1V = 1.1V
```

- **11** = 1.1V (standard starting point)
- **5** = 0.5V (very sensitive)
- **20** = 2.0V (requires more twist)

**Example:** At 1.1V, a slight twist begins assistance.

### `end_voltage`

**Allowed:** 0-255 (in 0.1V units)

Voltage at which throttle reaches 100% output:

```json
"end_voltage": 35  // 35 × 0.1V = 3.5V
```

- **35** = 3.5V (standard full throttle voltage)
- **25** = 2.5V (full power at lower twist)
- **50** = 5.0V (requires very large twist range)

**Example:** Between 1.1V and 3.5V, the motor ramps smoothly from 0% to 100%.

### `mode`

**Allowed:** 0, 1

Throttle assistance type:

```json
"mode": 1
```

| Value | Mode | Behavior |
|-------|------|----------|
| 0 | Speed Mode | Throttle target speed (rare) |
| **1** | Current Mode | Throttle provides direct current (common) |

**Example:** Mode 1 means twisting throttle directly controls motor current.

### `assist_level`

**Allowed:** 0-9, or **255** (By Display)

Which assist level to use with throttle:

```json
"assist_level": 255
```

- **255** = Use display's selected level
- **0-9** = Fixed level (throttle always uses this level's current limit)

**Example:** Setting to `5` means throttle always uses assist level 5's power envelope.

### `speed_limit`

**Allowed:** 0-27, or **255** (By Display)

Speed limit when using throttle:

```json
"speed_limit": 20  // 20 km/h maximum
```

- **255** = Use BAS block's speed limit
- **20-25** = Typical legal limit
- **0** = Throttle disabled

**Example:** Setting to `20` limits throttle to 20 km/h even if pedal assist allows more.

### `start_current_pct`

**Allowed:** 0-255 (%)

Current at minimum throttle position:

```json
"start_current_pct": 10
```

- **0%** = No current until throttle fully engaged
- **10%** = Small current even at rest position
- **50%** = Significant base current

**Example:** Setting to `10` means even a slight throttle twist provides some power.

---

## Common Mistakes to Avoid

1. **Wrong wheel_diameter_code** - Speed will be completely wrong
2. **assist_speed_limits over 100** - Values must be 0-100%
3. **All speeds set to 0** - No assistance at all
4. **speed_meter_signals = 0** - Motor won't run
5. **start_voltage >= end_voltage** - Throttle won't work properly
6. **Mixing 255 special values** - May cause unexpected behavior with your display

---

## Useful References

- **Motor Max Speed (SW09 @ 48V):** ~31 km/h at 100%
- **EU Legal Assist Speed:** 25 km/h (≈ 80% setting)
- **Typical Throttle Range:** 1.1V to 3.5V
- **Standard Wheel Codes:** 52 (26"), 56 (28"), others per table above
- **"By Display" (255):** Lets your LCD display control that setting

Further explanation of parameters: [A Hacker’s Guide To Programming The BBS02 & BBSHD](https://electricbike-blog.com/2015/06/26/a-hackers-guide-to-programming-the-bbs02/)
