import asyncio
import sys

import east_asian_spacing
import east_asian_spacing.ttc


def main():
    args = sys.argv
    if len(args) > 1:
        sub_command = args[1]
        if sub_command == 'dump' or sub_command == 'd':
            del args[1]
            asyncio.run(east_asian_spacing.Dump.main())
            return

        if sub_command == 'ttc':
            del args[1]
            east_asian_spacing.ttc.main()
            return

    asyncio.run(east_asian_spacing.Builder.main())


if __name__ == '__main__':
    main()
