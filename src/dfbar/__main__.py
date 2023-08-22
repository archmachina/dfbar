from .dfbar import main
import sys

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(e)
        sys.exit(1)

    sys.exit(0)
