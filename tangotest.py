

from tango_class import Tango


tango = Tango()

try:
    tango.demo()

finally:
    tango.close()
