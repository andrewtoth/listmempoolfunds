import os
import unittest
from pyln.testing.fixtures import *
from pyln.testing.utils import DEVELOPER, BITCOIND_CONFIG, sync_blockheight

plugin_path = os.path.join(os.path.dirname(__file__), 'listmempoolfunds.py')
desc1 = 'wpkh(tpubD6NzVbkrYhZ4XWDjRrgm3AVzsYbxmquiE1YZEYQrVdnrNSjjWgDLi6X3SuMZK7R38GJD72d9Prgrfy6fc4aTPkpkFgN3SfKmWUyRNqgsTsg/0/0/*)#0854uw77'
desc2 = 'sh(wpkh(tpubD6NzVbkrYhZ4XWDjRrgm3AVzsYbxmquiE1YZEYQrVdnrNSjjWgDLi6X3SuMZK7R38GJD72d9Prgrfy6fc4aTPkpkFgN3SfKmWUyRNqgsTsg/0/0/*))#ue2wpnz2'
bip32_seed = '8940A3407DCA074B19C1CA2F784C95776198D3353D6EE00CCA9741E606313087'

def check_output(txid, addr, amount, output):
    assert output['txid'] == txid, 'Output is different than txid'
    assert output['value'] == amount, 'Value is different'
    assert output['amount_msat'] == amount * 10**3, 'Msat is different'
    assert output['address'] == addr, 'Address is different'

@unittest.skipIf(not DEVELOPER, "Need dev-force-bip32-seed")
def test_listmempoolfunds_start(node_factory, bitcoind):
    opts = {
        'plugin': plugin_path,
        'listmempoolfunds-rpcuser': BITCOIND_CONFIG['rpcuser'],
        'listmempoolfunds-rpcpassword': BITCOIND_CONFIG['rpcpassword'],
        'listmempoolfunds-rpcport': bitcoind.rpcport,
        'listmempoolfunds-descriptor': [desc1, desc2],
        'dev-force-bip32-seed': bip32_seed
    }
    l1 = node_factory.get_node(options=opts)
    l1.daemon.wait_for_logs(['Created wallet.*',
                             'Imported descriptor .*',
                             'Imported descriptor .*',
                             'Rescanning blockchain. Check bitcoind logs for progress.*'])
    l1.restart()
    l1.daemon.wait_for_log('Wallet .* already loaded.*')

    addr = l1.rpc.newaddr()['bech32']
    amount = 5 * 10**7

    # Unload second wallet to send from original wallet without having to change proxy url
    wallets = bitcoind.rpc.listwallets()
    bitcoind.rpc.unloadwallet(wallets[1])
    txid = bitcoind.rpc.sendtoaddress(addr, amount / 10**8)
    bitcoind.rpc.loadwallet(wallets[1])

    # Check no unconfirmed txs in listfunds
    outputs = l1.rpc.listfunds()['outputs']
    assert len(outputs) == 0, 'listfunds has unconfirmed output'

    # Check correct output in listmempoolfunds
    outputs = l1.rpc.listmempoolfunds()['outputs']
    assert len(outputs) == 1, 'listmempoolfunds has no unconfirmed output'
    output = outputs[0]
    check_output(txid, addr, amount, output)
    assert output['status'] == 'unconfirmed', 'Status is not unconfirmed'

    # Mine the tx
    bitcoind.rpc.unloadwallet(wallets[1])
    bitcoind.generate_block(1)
    bitcoind.rpc.loadwallet(wallets[1])
    sync_blockheight(bitcoind, [l1])

    # Check listfunds and listmempoolfunds are the same
    outputs = l1.rpc.listfunds()['outputs']
    assert len(outputs) == 1, 'listfunds does not have confirmed output'
    check_output(txid, addr, amount, outputs[0])
    assert outputs[0]['status'] == 'confirmed', 'Status is not confirmed'

    outputs = l1.rpc.listmempoolfunds()['outputs']
    assert len(outputs) == 1, 'listmempoolfunds does not have confirmed output'
    check_output(txid, addr, amount, outputs[0])
    assert outputs[0]['status'] == 'confirmed', 'Status is not confirmed'
