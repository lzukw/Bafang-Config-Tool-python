# Bafang-Config-Tool-python

A Tool to configure Bafang middle-Motors BBS01, BBS02, BBSHD and BBS03.

This tool is a command-line-tool written in python and should run on any platform that supports python. 

The tool was tested on Linux with a Bafang BBS02 48V 750W Motor. It should work with other Bafang motors as well, but this is not tested yet.

The serial-communication-protocol was reverse-engineered by reading the Source-code of [Peter Pennof's Bafang-Config-Tool for Windows](https://penoff.me/2016/01/13/e-bike-conversion-software/) written in Pascal. (Link viewed on 2026-05-11).

## Connecting the Programming Cable

You need a programming cable to connect the motor to your computer. You can find them on ebay or amazon by searching for "Bafang programming cable". A foto of the cable can be found on [ElectricBike-Blog.com](https://electricbike-blog.com/2015/03/17/programming-the-bbs02-without-frying-your-controller-and-losing-your-sanity/) (Link viewed on 2026-05-11). But you can also build your own cable. See [docs/serial_cable.md](docs/serial_cable.md) for more information.

The cable normally connected to the display must be connected to the programming cable (green, round plug). The other end of the programming cable (USB) must be connected to your computer. Then the battery must be connected to the motor. After that you can run the tool.

## Usage

On Linux your user must be member of the `dialout`-group to access the serial port without sudo-rights. You can add your user to this group with the following command, and then have to reboot:

```bash
sudo usermod -a -G dialout $USER
```

First read the Parameters from the controller with the command:

```bash
$ python3 bafang_config_tool.py read /dev/ttyUSB0 original_config.json
```

This will save the parameters to a file called `original_config.json`. For reference, the parameters of an unmodified BBS02 48V 750W Motor controller are also included in the repository as `original_48V-750W-controller_params.json`.

Next create a copy of this file.

```bash
$ cp original_config.json desired_motor_params.json
```

Edit this file with a text editor and change the parameters you want to change. You can find a description of the parameters in [docs/values-for-parameters.md](docs/values-for-parameters.md). After you have changed the parameters, you can write them back to the controller with the command:

```bash
$ python3 bafang_config_tool.py write /dev/ttyUSB0 desired_motor_params.json
```

If everything went well, you should see "SUCCESS"-messages.

Lastly, it is recommended to read back the parameters from the controller and compare them with the file you wrote to the controller to make sure that everything was written correctly.

```bash
$ python3 bafang_config_tool.py read /dev/ttyUSB0 actual_motor_config.json
diff desired_motor_params.json actual_motor_config.json
```

## Disclaimer

This tool is provided "as is" without any warranty. The author is not responsible for any damage to your motor or other components that may occur while using this tool. Use it at your own risk.

This is my first project using mostly AI (github copilot) to extract information from the original Pascal-code and to write the python-code. I reviewed most parts of the code, and tested it with my motor, but there may still be bugs in the code. If you find any bugs, please report them to me. 
