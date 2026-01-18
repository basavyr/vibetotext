#!/usr/bin/env python3
"""Interactive configuration script for VibeToText."""

import json
import os
import sys
from pathlib import Path
try:
    import sounddevice as sd
except ImportError:
    print("Error: sounddevice not installed. Please run: pip install sounddevice")
    sys.exit(1)


def get_audio_devices():
    """Get list of available audio input devices."""
    try:
        devices = sd.query_devices()
        input_devices = []
        
        for i, dev in enumerate(devices):
            if dev['max_input_channels'] > 0:
                input_devices.append({
                    'index': i,
                    'name': dev['name'],
                    'channels': dev['max_input_channels'],
                    'sample_rate': int(dev['default_samplerate']) if dev['default_samplerate'] > 0 else 44100
                })
        
        return input_devices
    except Exception as e:
        print(f"Error getting audio devices: {e}")
        return []


def get_whisper_models():
    """Get available Whisper.cpp model options."""
    return [
        # Tiny models
        {'name': 'tiny', 'size': '~39MB', 'speed': 'Fastest', 'accuracy': 'Lowest'},
        {'name': 'tiny.en', 'size': '~39MB', 'speed': 'Fastest', 'accuracy': 'Lowest (English only)'},
        {'name': 'tiny-q5_1', 'size': '~49MB', 'speed': 'Fast', 'accuracy': 'Low'},
        {'name': 'tiny.en-q5_1', 'size': '~49MB', 'speed': 'Fast', 'accuracy': 'Low (English only)'},
        {'name': 'tiny-q8_0', 'size': '~78MB', 'speed': 'Fast', 'accuracy': 'Low'},
        {'name': 'tiny.en-q8_0', 'size': '~78MB', 'speed': 'Fast', 'accuracy': 'Low (English only)'},
        
        # Base models
        {'name': 'base', 'size': '~74MB', 'speed': 'Fast', 'accuracy': 'Good'},
        {'name': 'base.en', 'size': '~74MB', 'speed': 'Fast', 'accuracy': 'Good (English only)'},
        {'name': 'base-q5_1', 'size': '~94MB', 'speed': 'Fast', 'accuracy': 'Good'},
        {'name': 'base.en-q5_1', 'size': '~94MB', 'speed': 'Fast', 'accuracy': 'Good (English only)'},
        {'name': 'base-q8_0', 'size': '~149MB', 'speed': 'Medium', 'accuracy': 'Better'},
        {'name': 'base.en-q8_0', 'size': '~149MB', 'speed': 'Medium', 'accuracy': 'Better (English only)'},
        
        # Small models
        {'name': 'small', 'size': '~244MB', 'speed': 'Medium', 'accuracy': 'Better'},
        {'name': 'small.en', 'size': '~244MB', 'speed': 'Medium', 'accuracy': 'Better (English only)'},
        {'name': 'small-q5_1', 'size': '~306MB', 'speed': 'Medium', 'accuracy': 'Good'},
        {'name': 'small.en-q5_1', 'size': '~306MB', 'speed': 'Medium', 'accuracy': 'Good (English only)'},
        {'name': 'small-q8_0', 'size': '~489MB', 'speed': 'Slow', 'accuracy': 'Better'},
        {'name': 'small.en-q8_0', 'size': '~489MB', 'speed': 'Slow', 'accuracy': 'Better (English only)'},
        
        # Medium models
        {'name': 'medium', 'size': '~769MB', 'speed': 'Slow', 'accuracy': 'Good'},
        {'name': 'medium.en', 'size': '~769MB', 'speed': 'Slow', 'accuracy': 'Good (English only)'},
        {'name': 'medium-q5_0', 'size': '~961MB', 'speed': 'Slow', 'accuracy': 'Good'},
        {'name': 'medium.en-q5_0', 'size': '~961MB', 'speed': 'Slow', 'accuracy': 'Good (English only)'},
        {'name': 'medium-q8_0', 'size': '~1.5GB', 'speed': 'Slower', 'accuracy': 'Better'},
        {'name': 'medium.en-q8_0', 'size': '~1.5GB', 'speed': 'Slower', 'accuracy': 'Better (English only)'},
        
        # Large models
        {'name': 'large-v1', 'size': '~1550MB', 'speed': 'Slowest', 'accuracy': 'Best'},
        {'name': 'large-v2', 'size': '~1550MB', 'speed': 'Slowest', 'accuracy': 'Best'},
        {'name': 'large-v2-q5_0', 'size': '~1.9GB', 'speed': 'Slowest', 'accuracy': 'Best'},
        {'name': 'large-v2-q8_0', 'size': '~3.1GB', 'speed': 'Slowest', 'accuracy': 'Best'},
        {'name': 'large-v3', 'size': '~1550MB', 'speed': 'Slowest', 'accuracy': 'Best'},
        {'name': 'large-v3-q5_0', 'size': '~1.9GB', 'speed': 'Slowest', 'accuracy': 'Best'},
        {'name': 'large-v3-turbo', 'size': '~774MB', 'speed': 'Slow', 'accuracy': 'Best'},
        {'name': 'large-v3-turbo-q5_0', 'size': '~970MB', 'speed': 'Slow', 'accuracy': 'Best'},
        {'name': 'large-v3-turbo-q8_0', 'size': '~1.6GB', 'speed': 'Slower', 'accuracy': 'Best'},
    ]


def prompt_choice(prompt, options, display_func=None, allow_empty=False):
    """Prompt user to choose from options."""
    while True:
        print(f"\n{prompt}")
        for i, option in enumerate(options, 1):
            if display_func:
                display_func(i, option)
            else:
                print(f"  [{i}] {option}")
        
        if allow_empty:
            print("  [0] Keep current/default")
            choice = input("\nEnter choice (0-{}): ".format(len(options)))
        else:
            choice = input("\nEnter choice (1-{}): ".format(len(options)))
        
        try:
            choice_num = int(choice)
            if allow_empty and choice_num == 0:
                return None
            elif 1 <= choice_num <= len(options):
                return options[choice_num - 1]
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a valid number.")


def display_audio_device(index, device):
    """Display audio device info."""
    marker = ""
    try:
        default_idx = sd.default.device[0]
        if device['index'] == default_idx:
            marker = " (DEFAULT)"
    except:
        pass
    print(f"  [{index}] {device['name']}{marker}")
    print(f"      Channels: {device['channels']}, Sample Rate: {device['sample_rate']}Hz")


def display_whisper_model(index, model):
    """Display Whisper model info."""
    print(f"  [{index}] {model['name']}")
    print(f"      Size: {model['size']}, Speed: {model['speed']}, Accuracy: {model['accuracy']}")


def load_config():
    """Load existing configuration."""
    config_file = Path.home() / ".vibetotext" / "config.json"
    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(config):
    """Save configuration to file."""
    config_dir = Path.home() / ".vibetotext"
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / "config.json"
    
    try:
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
        print(f"\nConfiguration saved to: {config_file}")
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False


def main():
    """Main configuration interface."""
    print("=== VibeToText Configuration ===\n")
    
    # Load existing config
    config = load_config()
    
    # Audio device selection
    print("1. Audio Device Selection")
    print("-" * 30)
    
    devices = get_audio_devices()
    if not devices:
        print("No audio input devices found!")
        return
    
    current_device = config.get('audio_device_index')
    if current_device is not None:
        try:
            current_device_obj = next(d for d in devices if d['index'] == current_device)
            print(f"Current device: {current_device_obj['name']} (index {current_device})")
        except:
            print(f"Current device: {current_device} (not found)")
    else:
        print("Current device: System default")
    
    selected_device = prompt_choice(
        "Select audio device:",
        devices,
        display_audio_device,
        allow_empty=True
    )
    
    # Whisper model selection
    print("\n2. Whisper Model Selection")
    print("-" * 30)
    
    models = get_whisper_models()
    current_model = config.get('whisper_model', 'base')
    print(f"Current model: {current_model}")
    
    selected_model = prompt_choice(
        "Select Whisper model:",
        models,
        display_whisper_model,
        allow_empty=True
    )
    
    # Hotkey configuration
    print("\n3. Hotkey Configuration")
    print("-" * 30)
    
    current_hotkeys = {
        'transcribe': config.get('hotkey', 'ctrl+shift'),
        'greppy': config.get('greppy_hotkey', 'cmd+shift'),
        'cleanup': config.get('cleanup_hotkey', 'alt+shift'),
        'plan': config.get('plan_hotkey', 'cmd+alt+p')
    }
    
    print("Current hotkeys:")
    for mode, hotkey in current_hotkeys.items():
        print(f"  {mode}: {hotkey}")
    
    configure_hotkeys = input("\nConfigure hotkeys? (y/N): ").strip().lower() == 'y'
    
    hotkeys = current_hotkeys.copy()
    if configure_hotkeys:
        print("\nEnter new hotkeys (or press Enter to keep current):")
        for mode in ['transcribe', 'greppy', 'cleanup', 'plan']:
            current = current_hotkeys[mode]
            new = input(f"  {mode} [{current}]: ").strip()
            if new:
                hotkeys[mode] = new
    
    # Additional settings
    print("\n4. Additional Settings")
    print("-" * 30)
    
    current_context_limit = config.get('context_limit', 5)
    current_greppy_limit = config.get('greppy_limit', 10)
    current_no_context = config.get('no_context', False)
    
    print(f"Current context limit: {current_context_limit}")
    print(f"Current greppy limit: {current_greppy_limit}")
    print(f"Disable context injection: {current_no_context}")
    
    configure_settings = input("\nConfigure additional settings? (y/N): ").strip().lower() == 'y'
    
    context_limit = current_context_limit
    greppy_limit = current_greppy_limit
    no_context = current_no_context
    
    if configure_settings:
        try:
            new_context = input(f"Context limit [{current_context_limit}]: ").strip()
            if new_context:
                context_limit = int(new_context)
            
            new_greppy = input(f"Greppy limit [{current_greppy_limit}]: ").strip()
            if new_greppy:
                greppy_limit = int(new_greppy)
            
            new_no_context = input(f"Disable context injection [{'y' if current_no_context else 'n'}]: ").strip().lower()
            if new_no_context:
                no_context = new_no_context in ['y', 'yes', '1']
        except ValueError:
            print("Invalid input, keeping current values.")
    
    # Build new config
    new_config = {}
    
    if selected_device:
        new_config['audio_device_index'] = selected_device['index']
        new_config['audio_device_name'] = selected_device['name']
    
    if selected_model:
        new_config['whisper_model'] = selected_model['name']
    
    if configure_hotkeys:
        new_config.update({
            'hotkey': hotkeys['transcribe'],
            'greppy_hotkey': hotkeys['greppy'],
            'cleanup_hotkey': hotkeys['cleanup'],
            'plan_hotkey': hotkeys['plan']
        })
    
    if configure_settings:
        new_config.update({
            'context_limit': context_limit,
            'greppy_limit': greppy_limit,
            'no_context': no_context
        })
    
    # Show summary
    print("\n5. Configuration Summary")
    print("-" * 30)
    
    if 'audio_device_name' in new_config:
        print(f"Audio device: {new_config['audio_device_name']} (index {new_config['audio_device_index']})")
    else:
        print("Audio device: No change")
    
    if 'whisper_model' in new_config:
        print(f"Whisper model: {new_config['whisper_model']}")
    else:
        print("Whisper model: No change")
    
    if configure_hotkeys:
        print("Hotkeys:")
        for mode in ['transcribe', 'greppy', 'cleanup', 'plan']:
            key = mode + '_hotkey' if mode != 'transcribe' else 'hotkey'
            print(f"  {mode}: {new_config[key]}")
    else:
        print("Hotkeys: No change")
    
    if configure_settings:
        print(f"Context limit: {new_config['context_limit']}")
        print(f"Greppy limit: {new_config['greppy_limit']}")
        print(f"Disable context: {new_config['no_context']}")
    else:
        print("Additional settings: No change")
    
    # Save configuration
    confirm = input("\nSave configuration? (Y/n): ").strip().lower()
    if confirm in ['', 'y', 'yes']:
        # Merge with existing config
        final_config = config.copy()
        final_config.update(new_config)
        
        if save_config(final_config):
            print("\n✅ Configuration saved successfully!")
            print("\nYou can now run vibetotext with these settings:")
            print("  vibetotext")
            print("\nOr override specific settings:")
            print("  vibetotext --model small --hotkey alt+shift")
        else:
            print("\n❌ Failed to save configuration.")
    else:
        print("\nConfiguration not saved.")


if __name__ == "__main__":
    main()