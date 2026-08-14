import time
from opencal.hardware.lcd_display import LCDDisplay
from opencal.utils.config import Config

def test_screen():
    print("Initializing configuration...")
    conf = Config()
    print("LCD Config:", conf.lcd_display)
    
    print("Creating LCDDisplay instance...")
    lcd = LCDDisplay(conf.lcd_display)
    
    print("Clearing screen...")
    lcd.clear()
    time.sleep(0.5)
    
    print("Writing messages...")
    lcd.write_message("OpenCAL V2 Ready!", 0)
    time.sleep(0.2)
    lcd.write_message("Newhaven 20x4 LCD", 1)
    time.sleep(0.2)
    lcd.write_message("Connected via I2C", 2)
    time.sleep(0.2)
    lcd.write_message("Status: 100% OK!", 3)
    
    print("Done! Check the physical LCD screen now.")

if __name__ == "__main__":
    test_screen()
