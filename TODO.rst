TODO
====

Musings of possible features/improvements.

support for DVM/boot2docker for OSX
-----------------------------------

It would be very nice to run natively from OSX. The Docker API calls
from Blockade will already work, perhaps with some minor changes. The
big problem is that Blockade runs ``iptables`` and ``tc`` locally. We
would need to go through Fabric perhaps in this case. Another option
is a Blockade Remote API that runs on the VM and is usable from an
OSX client (similar to how Docker itself works).


more flexible partitioning
--------------------------

It could be interesting to allow one way messages. One horror story I heard is
of a NIC failure such that outbound messages worked but not inbound. So the
machine kept sending heartbeats to other nodes.

It might also be valuable to allow complex partitions -- partitions with
overlapping views.
See: http://kellabyte.com/2014/02/09/routing-aware-master-elections/


python-iptables
---------------

Look into using ``python-iptables`` module for iptables interaction. It uses
a library instead of invoking and parsing the iptables binary. I tried it
initially but ran into weird failures and didn't have time to debug.
Preserved code::

    def clear_iptables(blockade_id):
        """Remove all iptables rules and chains related to this blockade
        """
        # first remove refererences to our custom chains
        filter_table = iptc.Table(iptc.Table.FILTER)
        forward_chain = iptc.Chain(filter_table, "FORWARD")
        for rule in list(forward_chain.rules):
            target = rule.target
            if target and target.name:

                # check if we have a partition chain name as target
                try:
                    parse_partition_index(blockade_id, target.name)
                except ValueError:
                    continue
                # and delete the rule if so
                forward_chain.delete_rule(rule)
                print "done"

        # then remove the chains themselves
        for chain in filter_table.chains:
            if chain.name.startswith(blockade_id):
                chain.flush()
                filter_table.delete_chain(chain)


    def partition_containers(blockade_id, partitions):
        if not partitions or len(partitions) == 1:
            return
        for index, partition in enumerate(partitions, 1):
            chain_name = partition_chain_name(blockade_id, index)
            filter_table = iptc.Table(iptc.Table.FILTER)

            # createe chain for partition and block traffic TO any other partition
            chain = filter_table.create_chain(chain_name)
            for other in partitions:
                if partition is other:
                    continue
                for container in other:
                    if container.ip_address:
                        rule = iptc.Rule()
                        rule.dst = container.ip_address
                        rule.create_target("DROP")
                        chain.insert_rule(rule)

            # direct traffic FROM any container in the partition to the new chain
            forward_chain = iptc.Chain(filter_table, "FORWARD")
            for container in partition:
                rule = iptc.Rule()
                rule.src = container.ip_address
                rule.create_target(chain_name)
                forward_chain.insert_rule(rule)
