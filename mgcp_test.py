import socket               # Import socket module
import getopt
import sys
import random
import re
import traceback

#globals
messages=""
gw_v6_mode=False
udp_mode=False
rtp_port_min=5000
rtp_port_max=5000
ca_mode = False

ca_addr = ""
ca_port = 0
gw_addr = ""
gw_port = 0
gw_proto=""

rtp_socket_list = [] # for fake rtp
msg_values_dic = {}  # for message values replacement

def usage():
    print(
        """useage:
        -f file  MGCP messages file
        -s       In ca mode
        """)

def load_message(file_name):
    global messages
    with open(file_name, 'r') as content_file:
        messages = content_file.read().splitlines()

def read_block(block_name):
    global messages
    block_name = "%"+block_name
    tag = False
    block=[]
    for line in messages:
        if line.startswith("\""):
            continue
        if tag and line == "%": # end of block
            break
        if tag:
            block.append(line)
        if block_name == line:
            tag = True
    return block

def load_setting():
    global gw_v6_mode
    global udp_mode
    global rtp_port_max
    global rtp_port_min

    global ca_addr
    global ca_port
    global gw_addr
    global gw_port
    global gw_proto

    try:
        setting = read_block("setting")
        for line in setting:
             if len(line) == 0:
                 continue
             if line.startswith("ca_ip="):
                 ca_addr = line[6:]
                 msg_values_dic["ca_ip"] = ca_addr
             elif line.startswith("ca_port="):
                 ca_port = int(line[8:])
                 msg_values_dic["ca_port"] = ca_port
             elif line.startswith("gw_ip="):
                 gw_addr = line[6:]
                 msg_values_dic["gw_ip"] = gw_addr
             elif line.startswith("gw_port="):
                 gw_port = int(line[8:])
                 msg_values_dic["gw_port"] = gw_port
             elif line.startswith("gw_proto="):
                 gw_proto = line[9:]
                 if gw_proto=="IP4":
                     gw_v6_mode = False
                 else:
                     gw_v6_mode = True
                 msg_values_dic["gw_proto"] = gw_proto
             elif line.startswith("udp_mode="):
                 udp_mode = eval(line[9:])
             elif line.startswith("rtp_port_min="):
                 rtp_port_min = int(line[13:])
                 msg_values_dic["rtp_port_min"] = rtp_port_min
             elif line.startswith("rtp_port_max="):
                 rtp_port_max = int(line[13:])
                 msg_values_dic["rtp_port_max"] = rtp_port_max
             else:
                 msg_values_dic[line.split("=")[0]] = line.split("=")[1]

    except:
        print "message file error"
        print msg_values_dic
        traceback.print_exc()
        sys.exit(2)


def rtp_fake():
    global rtp_socket_list
    print "faking rtp/rtcp"
    for s in rtp_socket_list:
        s[0].sendto("fake rtp/rtcp", s[1])

def get_rtp_port():
    global rtp_port_max
    global rtp_port_min
    return random.randrange(rtp_port_min, rtp_port_max, 2)

def msg_preprocess(message):
    result = ""
    rtp_port = get_rtp_port()
    for line in message:
        for key in msg_values_dic.keys():
            if key == "rtp_port":
                line = line.replace("$"+key, str(rtp_port))
            else:
                line = line.replace("$"+key, str(msg_values_dic[key]))
        result += line+"\n"
    return result

def ca_msg_preprocess(message):
    return msg_preprocess(message)

def gw_msg_preprocess(message):
    return msg_preprocess(message)

def ca_process_msg(message, addr):
    global ca_addr
    global ca_port
    p=re.compile("(?<=audio )\d+|(?<=video )\d+")
    for line in message:
        ports = p.findall(line)
        for port in ports:
            rtp_port = int(port)
            rtcp_port += 1
            s_rtp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  
            s_rtcp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  
            s_rtp.bind((ca_addr,0))
            s_rtcp.bind((ca_addr,0))
            rtp_socket_list.append((s_rtp,(addr, rtp_port)))
            rtp_socket_list.append((s_rtcp,(addr, rtcp_port)))


def run_ca():
    global ca_addr
    global ca_port
    addr = None

    if udp_mode:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  
        s.bind((ca_addr, ca_port)) 
    else:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  
        s.bind((ca_addr,ca_port))    # Bind to the port
        s.listen(5)                 # Now wait for gw connection.
        

    while True:
        # Establish connection with gw.
        if not udp_mode:
            c, addr = s.accept()
            msg = "%s:%d connected"%addr
        else:
            msg, addr = s.recvfrom(1024)
            udp_addr = addr

        sent=0
        received=0

        while True:
            if len(msg) != 0:
                print("<<<<<<<<<<<<<<<<<<")
                print(msg)
                received += 1
                ca_process_msg(msg,addr)
                rtp_fake()
                msg = ""
            else:
                if udp_mode:
                    c.close()
                else:
                    s.close()
                break

            msg_need_send = read_block("ca %d"%(sent))
            if len(msg_need_send) == 0:
                msg_need_send = read_block("ca %d@%d"%(sent,received))

            if len(msg_need_send) != 0:
                msg_need_send = ca_msg_preprocess(msg_need_send)
                print(">>>>>>>>>>>>>>>>>>")
                print(msg_need_send)
                if udp_mode:
                    s.sendto(msg_need_send, addr)
                else:
                    c.send(msg_need_send)
                sent += 1
                continue

            if udp_mode:
                msg, addr = s.recvfrom(1024)
                if addr != udp_addr: # new gw connected, reset state
                    sent=0
                    received=0
                    udp_addr = addr
            else:
                msg = c.recv(1024)


def gw_process_msg(msg):
    pass

def run_gw():
    global ca_addr
    global ca_port
    global gw_addr
    global gw_port

    address = (ca_addr, ca_port)

    if udp_mode:
        if gw_v6_mode:
            s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)  
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  
        s.bind((gw_addr, gw_port))
    else:
        if gw_v6_mode:
            s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)  
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  
        s.bind((gw_addr, gw_port))
        s.connect(address)

    sent = 0
    received = 0

    while True:
        msg_need_send = read_block("gw %d"%(sent))
        if len(msg_need_send) == 0:
            msg_need_send = read_block("gw %d@%d"%(sent,received))

        if len(msg_need_send) != 0:
            msg_need_send = gw_msg_preprocess(msg_need_send)
            print(">>>>>>>>>>>>>>>>>>")
            print(msg_need_send)
            if udp_mode:
                s.sendto(msg_need_send, address)
            else:
                s.send(msg_need_send)
            sent += 1
            continue

        msg = s.recv(1024)
        if len(msg) != 0:
            print("<<<<<<<<<<<<<<<<<<")
            print(msg)
            received += 1
            gw_process_msg(msg)
        else:
            s.close()
            break

def test_reset():
    global rtp_socket_list
    for s in rtp_socket_list:
        s[0].close()
    rtp_socket_list = []

def main(argv):
    global ca_mode
    message_file = ""

    try:
        opts, args = getopt.getopt(argv,"f:s")
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    for opt, arg in opts:
        if opt in ("-f","--file"):
            message_file = arg
        elif opt in ("-s","--server"):
            ca_mode = True
        else:
            usage()
            sys.exit(2)

    if len(message_file) == 0:
        usage()
        sys.exit(2)

    load_message(message_file)
    if len(message_file) == 0:
        sys.exit(0)
    load_setting()

    try:
        if ca_mode:
            run_ca()
        else:
            run_gw()
    except:
        print "exiting..."
        traceback.print_exc()
    test_reset()

main(sys.argv[1:])
