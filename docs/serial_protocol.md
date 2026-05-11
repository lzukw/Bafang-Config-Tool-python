# Bafang Controller Serial Protocol Documentation

## Overview

The Bafang SW09 motor controller communicates via a serial UART interface at **1200 baud**. This document describes the protocol used to read and write configuration parameters.

## Serial Connection Parameters

- **Baudrate:** 1200 baud
- **Data Bits:** 8
- **Stop Bits:** 1
- **Parity:** None
- **Flow Control:** None

## Frame Structure

All serial frames follow this structure:

```
[CMD_BYTE] [BLOCK_ID] [LENGTH] [DATA_0...DATA_N] [CHECKSUM]
```

### Byte Positions

| Position | Name | Description |
|----------|------|-------------|
| 0 | CMD_BYTE | Command type: `0x11` (read) or `0x16` (write) |
| 1 | BLOCK_ID | Parameter block identifier (see table below) |
| 2 | LENGTH | Number of data bytes (excluding CMD, BLOCK_ID, LENGTH, and CHECKSUM) |
| 3 to N | DATA | Parameter data bytes |
| N+1 | CHECKSUM | Modulo-256 sum of all bytes except CMD_BYTE |

### Checksum Calculation

```
checksum = (sum of bytes[1:N]) mod 256
```

The checksum covers bytes from index 1 onward (excluding the command byte at index 0).

## Block Identifiers

| Block ID | Name | Purpose | Data Length |
|----------|------|---------|------------|
| `0x51` | GEN | General/controller info (read-only) | 16 bytes |
| `0x52` | BAS | Basic motor assistance parameters | 24 bytes |
| `0x53` | PAS | Pedal assist sensor parameters | 11 bytes |
| `0x54` | THR | Throttle handle parameters | 6 bytes |

## Command Types

### Read Command

**Request Format:**
```
[0x11] [BLOCK_ID] [0x04] [0xB0] [CHECKSUM]
```

- For GEN block only, uses fixed sequence `0x04 0xB0`
- For other blocks, only `[0x11] [BLOCK_ID]` are typically sent

**Response Format:**
```
[BLOCK_ID] [LENGTH] [DATA_0...DATA_N] [CHECKSUM]
```

The controller responds with the requested block data.

### Write Command

**Request Format:**
```
[0x16] [BLOCK_ID] [LENGTH] [DATA_0...DATA_N] [CHECKSUM]
```

**Response Format:**
```
[BLOCK_ID] [STATUS_CODE]
```

The controller responds with just two bytes:
- Byte 0: The BLOCK_ID that was written
- Byte 1: Status/error code (0 = success, non-zero = error condition)

## Block Specifications

### GEN Block (0x51) - General Controller Info

**Read-Only.** Contains manufacturer, model, and version information.

| Byte | Length | Name | Description |
|------|--------|------|-------------|
| 2-5 | 4 | Manufacturer | ASCII string (e.g., "SZBF") |
| 6-9 | 4 | Model | ASCII string (e.g., "SW09") |
| 10 | 1 | Hardware Version (major) | ASCII character (e.g., '2') |
| 11 | 1 | Hardware Version (minor) | ASCII character (e.g., '0') |
| 12 | 1 | Firmware Version (major) | ASCII character |
| 13 | 1 | Firmware Version (minor) | ASCII character |
| 14 | 1 | Firmware Version (patch) | ASCII character |
| 15 | 1 | Firmware Version (build) | ASCII character |
| 16 | 1 | Nominal Voltage Code | 0=24V, 1=36V, 2=48V, 3=60V, 4=24-48V, 5=24-60V |
| 17 | 1 | Maximum Current | Amps |

### BAS Block (0x52) - Basic Parameters

**24 data bytes.** Motor assistance and speed configuration.

| Byte | Name | Range | Unit | Description |
|------|------|-------|------|-------------|
| 2 | Low Battery Protection | 18-55 | V | Voltage cutoff for low battery |
| 3 | Current Limit | 0-255 | A | Maximum motor current |
| 4-13 | Assist Current Limits (0-9) | 0-255 | % | Current limit for each assist level |
| 14-23 | Assist Speed Limits (0-9) | 0-100 | % | Speed limit for each assist level |
| 24 | Wheel Diameter Code | 31-60 | - | Wheel size code (see values-for-parameters.md) |
| 25 | Speed Meter Type & Signals | Packed | - | Bits 7 and 6 = type, lower 6 bits = signals |

**Speed Meter Type & Signals Byte:**
- Type = (byte >> 6) & 0x03: 0=Wheel Meter, 1=Motor Meter, 3=Motor Phase
- Signals = byte & 0x3F: 1-63 signals per wheel rotation

### PAS Block (0x53) - Pedal Assist Parameters

**11 data bytes.** Pedal sensor and assist characteristics.

| Byte | Name | Range | Unit | Description |
|------|------|-------|------|-------------|
| 2 | Pedal Sensor Type | 0-3 | - | 0=None, 1=DH-12, 2=BB-32, 3=Double-24 |
| 3 | Designated Assist | 0-10, 255 | - | Assist level (255=by display) |
| 4 | Speed Limit | 0-27, 255 | km/h or % | Speed limit (255=by display) |
| 5 | Start Current | 1-20 | % | Initial assist current |
| 6 | Slow Start Mode | 1-8 | - | Ramp-up duration (1=slowest, 8=fastest) |
| 7 | Start Degree | 1-100 | deg | Pedal rotation before assist starts |
| 8 | Work Mode | 10-80, 255 | RPM | Assist mode (255=undetermined/cadence) |
| 9 | Stop Delay | 0-255 | x100ms | Time to continue assist after pedal stops |
| 10 | Current Decay | 0-255 | - | Assist power fade-out |
| 11 | Stop Decay | 0-255 | x100ms | Time to stop assist after threshold |
| 12 | Keep Current | 0-255 | % | Maintain assist current level |

### THR Block (0x54) - Throttle Parameters

**6 data bytes.** Throttle handle voltage range and assist settings.

| Byte | Name | Range | Unit | Description |
|------|------|-------|------|-------------|
| 2 | Start Voltage | 0-255 | x0.1V | Throttle voltage for 0% (e.g., 11 = 1.1V) |
| 3 | End Voltage | 0-255 | x0.1V | Throttle voltage for 100% (e.g., 35 = 3.5V) |
| 4 | Mode | 0-1 | - | 0=Speed mode, 1=Current mode |
| 5 | Assist Level | 0-10, 255 | - | Fixed assist level (255=by display) |
| 6 | Speed Limit | 0-27, 255 | km/h or % | Speed limit (255=by display) |
| 7 | Start Current | 0-255 | % | Initial motor current when throttle engaged |

## Write Response Status Codes

After a write command, the controller responds with two bytes: the BLOCK_ID and a status code indicating success or the type of error. The specific codes depend on the block being written.

### BAS Block Error Codes (0x52)

| Code | Message |
|------|---------|
| 0 | Low Battery Protection out of range |
| 1 | Current Limit out of range |
| 2-21 | Current or Speed Limit for assist level 0-9 out of range |
| 22 | Wheel Diameter out of range |
| 23 | Speed Meter Signals out of range |
| 24 | **Success: Basic flash write successful** |

### PAS Block Error Codes (0x53)

| Code | Message |
|------|---------|
| 0 | Pedal Sensor Type error |
| 1 | Designated Assist Level error |
| 2 | Speed Limit error |
| 3 | Start Current out of range |
| 4 | Slow-start Mode error |
| 5 | Start Degree out of range |
| 6 | Work Mode error |
| 7 | Stop Delay out of range |
| 8 | Current Decay out of range |
| 9 | Stop Decay out of range |
| 10 | Keep Current out of range |
| 11 | **Success: Pedal Assist flash write successful** |

### THR Block Error Codes (0x54)

| Code | Message |
|------|---------|
| 0 | Start Voltage out of range |
| 1 | End Voltage out of range |
| 2 | Mode error |
| 3 | Designated Assist error |
| 4 | Speed Limit error |
| 5 | Start Current out of range |
| 6 | **Success: Throttle Handle flash write successful** |

## Timing and Delays

- **Read Request Delay:** 200ms before sending request
- **Read Response Wait:** 200ms after flush
- **Write Request Delay:** 200ms before sending request
- **Write Response Wait:** 1000ms after flush (write takes longer)
- **Between Operations:** 200ms delay before next operation

## Example: Reading GEN Block

**Request (5 bytes):**
```
11 51 04 B0 06
```

**Response (20 bytes):**
```
51 10 53 5A 42 46 53 57 30 39 32 2E 30 01 00 00
04 01 00 02 12
```

Decoding:
- `51 10` = GEN block, 16 data bytes
- `53 5A 42 46` = "SZ BF" (with spaces, actually "SZBF")
- `53 57 30 39` = "SW09" 
- `32 2E 30` = "2.0" (hardware version)
- `01 00 00 04` = firmware version 1.0.0.4
- `01` = 36V (code 1)
- `12` = 18A max current

## Example: Writing BAS Block

**Request (28 bytes):**
```
16 52 18 [24 bytes of data] [checksum]
```

**Response (2 bytes):**
```
52 18
```

Decoding:
- `52` = BAS block
- `18` = 24 (decimal) = success code for BAS

---

**Notes:**
- All multi-byte values are transmitted byte-by-byte in the order specified
- The controller processes writes atomically (full validation before committing)
- After a successful write, reading the block confirms the changes were persisted
