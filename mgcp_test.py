import socket               # Import socket module
import getopt
import sys
import random
import re
import traceback

#globals
gw_v6_mode=False
udp_mode=False
ca_mode = False

ca_addr    = ""
ca_port    = 0

gw_proto   = ""
gw_ca_addr = ""  # the ca address seen by gw
gw_ca_port = 0
gw_addr    = ""
gw_port    = 0

messages=""

class bcolors:
    HEADER    = '\033[95m'
    OKBLUE    = '\033[94m'
    OKGREEN   = '\033[92m'
    WARNING   = '\033[93m'
    FAIL      = '\033[91m'
    ENDC      = '\033[0m'
    BOLD      = '\033[1m'
    UNDERLINE = '\033[4m'

rtp_socket_list = [] # for fake rtp
msg_values_dic = {}  # for message values replacement

def usage():
    print(
        """usage:
        -f file  MGCP messages file
        -s       In ca mode
        """)

def rtp_socket_list_reset():
    global rtp_socket_list
    for s in rtp_socket_list:
        s[0].close()
    rtp_socket_list = []

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
    global ca_addr
    global ca_port
    global gw_addr
    global gw_port
    global gw_proto
    global gw_ca_addr
    global gw_ca_port

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
             elif line.startswith("gw_ca_ip="):
                 gw_ca_addr = line[9:]
                 msg_values_dic["gw_ca_ip"] = gw_addr
             elif line.startswith("gw_ca_port="):
                 gw_ca_port = int(line[11:])
                 msg_values_dic["gw_ca_port"] = gw_port
             elif line.startswith("udp_mode="):
                 udp_mode = eval(line[9:])
             else:
                 msg_values_dic[line.split("=")[0]] = line.split("=")[1]

        if len(gw_ca_addr) == 0:
            gw_ca_addr = ca_addr # use default value
            gw_ca_port = ca_port
    except:
        print bcolors.FAIL + "message file error" + bcolors.ENDC
        print msg_values_dic
        traceback.print_exc()
        sys.exit(2)


def rtp_fake():
    global rtp_socket_list
    for s in rtp_socket_list:
        s[0].sendto("fake rtp/rtcp", s[1])
        print "Send fake rtp/rtcp to[%s]:%d"%s[1]

def msg_preprocess(message):
    result = ""
    for line in message:
        for key in msg_values_dic.keys():
            line = line.replace("$"+key, str(msg_values_dic[key]))
        result += line+"\n"
    return result

def ca_msg_preprocess(message):
    return msg_preprocess(message)

def gw_msg_preprocess(message):
    return msg_preprocess(message)

def get_rtp_addr(sdp_message):
    addr=None
    for line in sdp_message:
        if line.startswith("c=IN IP"):
            addr = line[9:].split(" ")[0]
    return addr

def get_rtp_ports(sdp_message):
    ports = []
    p=re.compile("(?<=audio )\d+|(?<=video )\d+")
    for line in sdp_message:
        ports_str = p.findall(line)
        for port in ports_str:
            ports.append(int(port))
    return ports

def ca_process_msg(message, addr):
    global ca_addr
    global rtp_socket_list

    message = message.splitlines()

    rtp_dst_addr = get_rtp_addr(message)
    if not rtp_dst_addr:
        return
    if rtp_dst_addr != addr[0]:
        print bcolors.WARNING + "Warnning: [%s] != [%s]"%(rtp_dst_addr, addr[0]) +bcolors.ENDC

    rtp_ports = get_rtp_ports(message)
    for rtp_port in rtp_ports:
        s_rtp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  
        s_rtp.bind((ca_addr,0))
        rtp_socket_list.append((s_rtp,(rtp_dst_addr, rtp_port)))
        rtcp_port = rtp_port + 1
        s_rtcp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  
        s_rtcp.bind((ca_addr,0))
        rtp_socket_list.append((s_rtcp,(rtp_dst_addr, rtcp_port)))

def valid_msg(message):
    return (len(message) > 4)

def print_input_msg(msg):
    print("<<<<<<<<<<<<<<<<<<")
    print(bcolors.OKBLUE + msg + bcolors.ENDC)

def print_output_msg(msg):
    print(">>>>>>>>>>>>>>>>>>")
    print(bcolors.BOLD + msg + bcolors.ENDC)

def msg_num_received_from_tcp(msg):
    num = 0
    contains_invalid = False
    messages = msg.splitlines()
    message = ""
    for line in messages:
        if line == "%":
            num +=1
            if not valid_msg(message):
                contains_invalid = True
            message = ""
        message += line
    return (num,contains_invalid)


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
        

    try:
        while True:
            sent=0
            received=0
            at_received = received
            # Establish connection with gw.
            if not udp_mode:
                c, addr = s.accept()
                msg = c.recv(1024)
                msg_num, contains_invalid = msg_num_received_from_tcp(msg)
                received += msg_num
            else:
                msg, addr = s.recvfrom(1024)
                udp_addr = addr
                received += 1
            print "%s:%d connected"%addr
            rtp_socket_list_reset()

            if valid_msg(msg):
                print_input_msg(msg)
                ca_process_msg(msg,addr)
                rtp_fake()

            while True:
                msg_need_send = read_block("ca %d"%(sent))
                while len(msg_need_send) == 0 and at_received <= received:
                    msg_need_send = read_block("ca %d@%d"%(sent, at_received-1))
                    at_received += 1

                if len(msg_need_send) != 0:
                    msg_need_send = ca_msg_preprocess(msg_need_send)
                    print_output_msg(msg_need_send)
                    if udp_mode:
                        s.sendto(msg_need_send, addr)
                    else:
                        c.send(msg_need_send+"\n%\n") # mark end of a message
                    sent += 1
                    if not valid_msg(msg_need_send):
                        if not udp_mode:
                            c.close()
                        print "connection closed"
                        break
                    continue


                if udp_mode:
                    msg, addr = s.recvfrom(1024)
                    if not valid_msg(msg):
                        break;
                    received += 1
                    if addr != udp_addr: # new gw connected, reset state
                        sent = 0
                        received = 1
                        at_received = received
                        udp_addr = addr
                        rtp_socket_list_reset()
                        print "%s:%d connected"%addr
                else:
                    msg = c.recv(1024)
                    if not valid_msg(msg):
                        c.close()
                        print "connection closed"
                        break;
                    msg_num, contains_invalid = msg_num_received_from_tcp(msg)
                    received += msg_num

                print_input_msg(msg)
                ca_process_msg(msg,addr)
                rtp_fake()

                if (not udp_mode) and contains_invalid:
                    c.close()
                    print "connection closed"
                    break
    except KeyboardInterrupt:
        print "canceling..."
    finally:
        s.close()
        print "socket closed"

def gw_process_msg(message):
    global rtp_socket_list
    global gw_addr
    global gw_ca_addr

    message = message.splitlines()

    rtp_dst_addr = get_rtp_addr(message)
    if not rtp_dst_addr:
        return
    if rtp_dst_addr != gw_ca_addr:
        print "Warnning: %s!=%s"%(rtp_dst_addr, gw_ca_addr)

    rtp_ports = get_rtp_ports(message)
    for rtp_port in rtp_ports:
        if gw_v6_mode:
            s_rtp = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)  
        else:
            s_rtp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  
        s_rtp.bind((gw_addr,0))
        rtp_socket_list.append((s_rtp,(rtp_dst_addr, rtp_port)))
        rtcp_port = rtp_port + 1
        if gw_v6_mode:
            s_rtcp = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)  
        else:
            s_rtcp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  
        s_rtcp.bind((gw_addr,0))
        rtp_socket_list.append((s_rtcp,(rtp_dst_addr, rtcp_port)))


def run_gw():
    global gw_ca_addr
    global gw_ca_port
    global gw_addr
    global gw_port

    address = (gw_ca_addr, gw_ca_port)

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
    at_received = received
    try:
        while True:
            msg_need_send = read_block("gw %d"%(sent))
            while len(msg_need_send) == 0 and at_received <= received:
                msg_need_send = read_block("gw %d@%d"%(sent,at_received-1))
                at_received += 1

            if len(msg_need_send) != 0:
                msg_need_send = gw_msg_preprocess(msg_need_send)
                print_output_msg(msg_need_send)
                if udp_mode:
                    s.sendto(msg_need_send, address)
                else:
                    s.send(msg_need_send + "\n%\n") #mark end of a message
                sent += 1
                if not valid_msg(msg_need_send):
                    break
                continue


            msg = s.recv(1024)
            if not valid_msg(msg):
                break

            if udp_mode:
                received += 1
            else:
                msg_num, contains_invalid = msg_num_received_from_tcp(msg)
                received += msg_num

            print_input_msg(msg)
            gw_process_msg(msg)
            rtp_fake()

            if (not udp_mode) and contains_invalid:
                break

    except KeyboardInterrupt:
        print "canceling..."
        if udp_mode:
            s.sendto("c\n", address) #close udp connection
    finally:
        s.close()
        print "socket closed"



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
    rtp_socket_list_reset()

main(sys.argv[1:])
