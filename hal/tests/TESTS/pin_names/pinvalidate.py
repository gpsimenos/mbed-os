"""
Copyright (c) 2020 ARM Limited

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import re
import argparse
import os
from tabulate import tabulate

def scan_pinName_files(target_name):
    targets = dict()
    for root, dirs, files in os.walk('.'):
        for f in files:
            if f == "PinNames.h":
                path = os.path.join(root, f)
                name = '_'.join(re.findall("TARGET_([a-zA-Z0-9_]*)\/", path))
                if not name:
                    continue
                if target_name:
                    if target_name not in name:
                        continue
                targets[name] = path
    return targets

def pinName_to_dict(pinName_file_content):
    pinName_enum_dict = dict()

    pinName_enum_match = re.search("typedef enum {\n([^}]*)\n} PinName;", pinName_file_content)
    if pinName_enum_match:
        pinName_enum_body = pinName_enum_match.group(1)
        pinName_enum_dict = dict(re.findall("^\s*([a-zA-Z0-9_]+)\s*=\s*([a-zA-Z0-9_]+)", pinName_enum_body, re.MULTILINE))
    
    pinName_define_dict = dict(re.findall("^#define\s+([a-zA-Z0-9_]+)\s+([a-zA-Z0-9_]+)", pinName_file_content, re.MULTILINE))
    
    return {**pinName_enum_dict, **pinName_define_dict}

def identity_assignment_check(pinName_dict):
    invalid_items = []
    for key, val in pinName_dict.items():
        if val == key:
            message = "cannot assign value to itself"
            invalid_items.append([key, val, message])
    return invalid_items

def nc_assignment_check(pinName_dict):
    invalid_items = []
    for key, val in pinName_dict.items():
        if re.match("^((LED|BUTTON)\d*|USBTX|USBRX)$", key):
            if val == 'NC':
                message = "cannot be NC"
                invalid_items.append([key, val, message])
    return invalid_items

def duplicate_assignment_check(pinName_dict):
    used_pins = []
    used_pins_friendly = []
    invalid_items = []

    for key, val in pinName_dict.items():
        if re.match("^((LED|BUTTON)\d*|USBTX|USBRX)$", key):
            if val == 'NC':
                continue
            # resolve to literal
            realval = val
            depth = 0
            while not re.match("(0x[0-9a-fA-F]+|[1-9][0-9]*|0[1-7][0-7]+|0b[01]+)[uUlL]{0,2}", realval):
                try:
                    realval = pinName_dict[realval]
                    depth += 1
                except:
                    break
                if depth > 10:
                    break

            if realval in used_pins:
                message = "already assigned to " + used_pins_friendly[used_pins.index(realval)]
                invalid_items.append([key, val, message])
                continue

            used_pins.append(realval)
            used_pins_friendly.append(key + ' = ' + val)
    return invalid_items

def arduino_duplicate_assignment_check(pinName_dict):
    used_pins = []
    used_pins_friendly = []
    invalid_items = []

    for key, val in pinName_dict.items():
        if re.match("^ARDUINO_UNO_[AD]\d+$", key):
            if val == 'NC':
                continue
            # resolve to literal
            realval = val
            depth = 0
            while not re.match("(0x[0-9a-fA-F]+|[1-9][0-9]*|0[1-7][0-7]+|0b[01]+)[uUlL]{0,2}", realval):
                try:
                    realval = pinName_dict[realval]
                    depth += 1
                except:
                    break
                if depth > 10:
                    break

            if realval in used_pins:
                message = "already assigned to " + used_pins_friendly[used_pins.index(realval)]
                invalid_items.append([key, val, message])
                continue

            used_pins.append(realval)
            used_pins_friendly.append(key + ' = ' + val)
    return invalid_items

def arduino_existence_check(pinName_dict):
    required_pins = [
        'ARDUINO_UNO_A0',
        'ARDUINO_UNO_A1',
        'ARDUINO_UNO_A2',
        'ARDUINO_UNO_A3',
        'ARDUINO_UNO_A4',
        'ARDUINO_UNO_A5',
        'ARDUINO_UNO_D0',
        'ARDUINO_UNO_D1',
        'ARDUINO_UNO_D2',
        'ARDUINO_UNO_D3',
        'ARDUINO_UNO_D4',
        'ARDUINO_UNO_D5',
        'ARDUINO_UNO_D6',
        'ARDUINO_UNO_D7',
        'ARDUINO_UNO_D8',
        'ARDUINO_UNO_D9',
        'ARDUINO_UNO_D10',
        'ARDUINO_UNO_D11',
        'ARDUINO_UNO_D12',
        'ARDUINO_UNO_D13',
        'ARDUINO_UNO_D14',
        'ARDUINO_UNO_D15'
    ]

    invalid_items = []

    for pin in required_pins:
        if pin not in pinName_dict:
            message = pin + " not defined"
            invalid_items.append([pin, '', message])
    
    return invalid_items

def arduino_nc_assignment_check(pinName_dict):
    invalid_items = []
    for key, val in pinName_dict.items():
        if re.match("^ARDUINO_UNO_[AD]\d+$", key):
            if val == 'NC':
                message = "cannot be NC"
                invalid_items.append([key, val, message])
    return invalid_items

def legacy_assignment_check(pinName_content):
    invalid_items = []
    legacy_assignments = dict(re.findall("^\s*((?:LED|BUTTON)\d*)\s*=\s*([a-zA-Z0-9_]+)", pinName_content, re.MULTILINE))
    for key, val in legacy_assignments.items():
        message = "legacy assignment; LEDs and BUTTONs must be #define'd"
        invalid_items.append([key, val, message])
    return invalid_items

def check_pinName_file(path, target_name, generic_checks, arduino_checks, verbosity):
    try:
        pinName_file = open(path)
        pinName_content = pinName_file.read()
    except:
        print("Cannot open file: " + path)
        return 1
    
    try:
        pinName_dict = pinName_to_dict(pinName_content)
    except:
        print("Cannot extract PinName enum from file: " + pinName_file)
        return 1
    
    target_report = []
    target_errors = []

    if generic_checks or not (generic_checks or arduino_checks):
        identity_errors = identity_assignment_check(pinName_dict)
        if identity_errors:
            target_report.append([target_name, 'Generic pin names', 'identity', 'FAILED', len(identity_errors)])
        else:
            target_report.append([target_name, 'Generic pin names', 'identity', 'PASSED', 0])
        target_errors += identity_errors

        nc_errors = nc_assignment_check(pinName_dict)
        if nc_errors:
            target_report.append([target_name, 'Generic pin names', 'NC', 'FAILED', len(nc_errors)])
        else:
            target_report.append([target_name, 'Generic pin names', 'NC', 'PASSED', 0])
        target_errors += nc_errors

        duplicate_errors = duplicate_assignment_check(pinName_dict)
        if duplicate_errors:
            target_report.append([target_name, 'Generic pin names', 'duplicate', 'FAILED', len(duplicate_errors)])
        else:
            target_report.append([target_name, 'Generic pin names', 'duplicate', 'PASSED', 0])
        target_errors += duplicate_errors

        legacy_errors = legacy_assignment_check(pinName_content)
        if legacy_errors:
            target_report.append([target_name, 'Generic pin names', 'legacy', 'FAILED', len(legacy_errors)])
        else:
            target_report.append([target_name, 'Generic pin names', 'legacy', 'PASSED', 0])
        target_errors += legacy_errors

    if arduino_checks or not (generic_checks or arduino_checks):
        arduino_existence_errors = arduino_existence_check(pinName_dict)
        if arduino_existence_errors:
            target_report.append([target_name, 'Arduino Uno', 'existence', 'FAILED', len(arduino_existence_errors)])
        else:
            target_report.append([target_name, 'Arduino Uno', 'existence', 'PASSED', 0])
        target_errors += arduino_existence_errors

        arduino_nc_errors = arduino_nc_assignment_check(pinName_dict)
        if arduino_nc_errors:
            target_report.append([target_name, 'Arduino Uno', 'NC', 'FAILED', len(arduino_nc_errors)])
        else:
            target_report.append([target_name, 'Arduino Uno', 'NC', 'PASSED', 0])
        target_errors += arduino_nc_errors

        arduino_duplicate_errors = arduino_duplicate_assignment_check(pinName_dict)
        if arduino_duplicate_errors:
            target_report.append([target_name, 'Arduino Uno', 'duplicate', 'FAILED', len(arduino_duplicate_errors)])
        else:
            target_report.append([target_name, 'Arduino Uno', 'duplicate', 'PASSED', 0])
        target_errors += arduino_duplicate_errors
    
    if verbosity > 0:
        print(tabulate(target_report, headers=['Platform name', 'Test suite', 'Test case', 'Result', 'Errors'], tablefmt='pretty'))

    if target_errors:
        if verbosity > 1:
            print(tabulate(target_errors, headers=['Pin', 'Value', 'Error'], tablefmt='pretty'))

    return len(target_errors)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", '--arduino', action="store_true", help="Run Arduino Uno test suite")
    parser.add_argument("-g", '--generic', action="store_true", help="Run Generic pin names test suite")
    parser.add_argument('-v', '--verbose', action='count', default=0)
    parser.add_argument("-t", '--target', help="Target name")
    parser.add_argument("-p", '--path', help="Path to PinNames.h file")
    args = parser.parse_args()

    if args.path:
        errors = check_pinName_file(args.path, '', args.generic, args.arduino, args.verbose)

        if errors > 0:
            print("Errors found in PinNames file")
            exit(1)
        else:
            print("PinNames file is valid")
            exit(0)
    
    targets = scan_pinName_files(args.target)

    errors_found = False
    report = []
    for target_name, path in targets.items():
        if args.verbose > 1:
            print("\n ==== Checking " + target_name + " ====")

        errors = check_pinName_file(path, target_name, args.generic, args.arduino, args.verbose)
        if errors:
            errors_found = True
            report.append([target_name, 'FAILED', errors, path])
        else:
            report.append([target_name, 'PASSED', 0, path])
        
        if args.verbose > 1:
            print(" ==== Check complete for " + target_name + " ====\n")
    
    print(tabulate(report, headers=['Platform name', 'Result', 'Errors', 'Path'], tablefmt='pretty'))

if __name__ == "__main__":
    main()