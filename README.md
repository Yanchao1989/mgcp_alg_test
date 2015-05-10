# mgcp_alg_test

simple test tool for mgcp alg function of nat device

gw (inside) <--->  AX (NAT device) <--->  ca (outside)

1. Custom message file: mgcp_test_msg.txt
   a. Message file contains blocks
   b. Block starts with %block_name, and ends with %
   c. gw messages are defined as gw block (%gw sent_count, %gw sent_count@recevied_count)
   d. ca messages are defined as ca block (%ca sent_count, %ca sent_count@recevied_count)
   e, sent_count@recevied_count message block only can be sent when got recevied_count number of messages

2. Run ca using:
    python mgcp_test.py -f mgcp_test_msg.txt -s

3. Run gw using:
    python mgcp_test.py -f mgcp_test_msg.txt


