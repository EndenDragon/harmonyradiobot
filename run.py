from harmony import HarmonyBot
import gc

def main():
    print("Starting...")
    hb = HarmonyBot()
    hb.run()
    gc.collect()

if __name__ == "__main__":
    main()