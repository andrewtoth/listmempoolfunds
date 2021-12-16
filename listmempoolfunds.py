#!/usr/bin/env python3
'''List received funds that are still in the mempool
'''
from pyln.client import Plugin
from decimal import Decimal
from socket import timeout

from bitcoin.rpc import Proxy, JSONRPCError, InvalidAddressOrKeyError

plugin = Plugin(dynamic=False)

@plugin.init()
def init(options: dict, configuration: dict, plugin: Plugin, **kwargs):
    info = plugin.rpc.getinfo()
    # Create a desriptor wallet named clightning-<alias>-<id> so it will be unique
    wallet_name = f'clightning-{info["alias"]}-{info["id"]}'
    host = options['listmempoolfunds-rpchost']
    user = options['listmempoolfunds-rpcuser']
    password = options['listmempoolfunds-rpcpassword']
    port = options.get('listmempoolfunds-rpcport')
    if port == 'null':
        network = configuration['network']
        if network == 'testnet':
            port = '18332'
        elif network == 'regtest':
            port = '18443'
        elif network == 'signet':
            port = '38332'
        else:
            port = '8332'

    plugin.service_url = f'http://{user}:{password}@{host}:{port}/wallet/{wallet_name}'
    proxy = Proxy(service_url=plugin.service_url)

    wallets: list
    try:
        wallets = proxy.call('listwallets')        
    except JSONRPCError as e:
        if e.args[0]['message'] == 'Method not found':
            plugin.log('Could not find listwallets method. Is the wallet enabled?', 'error')
            return { 'disable': 'Could not find listwallets method. Is the wallet enabled?' }
        plugin.log(e.args[0]['message'], 'error')
        return { 'disable': e.args[0]['message'] }
    except Exception as e:
        plugin.log(f'Could not connect to {plugin.service_url}\nPlease check all listmempoolfunds options.', 'error')
        return { 'disable': f'Could not connect to {plugin.service_url}\nPlease check all listmempoolfunds options.' }

    if wallet_name in wallets:
        plugin.log(f'Wallet {wallet_name} already loaded.')
        return {}
    else:
        try:
            proxy.call('loadwallet', wallet_name)
            plugin.log(f'Loaded wallet {wallet_name}.')
            return {}
        except JSONRPCError as e:
            if e.args[0]['code'] != -18: # Code -18 is returned if the wallet doesn't exist
                plugin.log(e.args[0]['message'], 'error')
                return { 'disable': e.args[0]['message'] }

    # Determine if we have the right descriptors
    raw_descs = options['listmempoolfunds-descriptor']
    num_descs = 2
    if len(raw_descs) != num_descs:
        plugin.log('Both descriptors were not included as options.', 'error')
        return { 'disable': 'Both descriptors were not included as options.' }

    # Check the descriptors so we don't create the wallet and then can't import
    descs = []
    for desc in raw_descs:
        try:
            proxy.call('getdescriptorinfo', desc)
        except InvalidAddressOrKeyError as e:
            plugin.log('Invalid descriptors. Check the network argument when dumping from hsmtool.', 'error')
            return { 'disable': 'Invalid descriptors. Check the network argument when dumping from hsmtool.' }
        descs.append({ 'desc': desc, 'timestamp': 'now' })
    
    # Create the wallet and import the descriptors
    try:
        proxy.call('createwallet', wallet_name, True, False, '', False, True, True, False)
        plugin.log(f'Created wallet {wallet_name}')

        resps = proxy.call('importdescriptors', descs)
        for i in range(num_descs):
            if resps[i]['success']:
                plugin.log(f'Imported descriptor {raw_descs[i]}.')
            else:
                plugin.log(f'Failed to import descriptor {raw_descs[i]}: {resps[i]["error"]["message"]}')
        
        plugin.log('Rescanning blockchain. Check bitcoind logs for progress.')
        proxy.call('rescanblockchain', 481824) # Rescan at segwit block height
    except JSONRPCError as e:
        plugin.log(e.args[0]['message'], 'error')
    except timeout:
        # rescanblockchain only returns after it's finished, so just catch the socket timeout instead of waiting
        pass

    return {}

@plugin.method('listmempoolfunds')
def list_mempool_funds(plugin: Plugin, spent=False):
    """Show available funds from the internal wallet.
    Identical to listfunds, but also includes received funds that are still in the mempool.
    """
    listfunds_resp = plugin.rpc.listfunds(spent)
    txids = list(map(lambda unspent: unspent['txid'], listfunds_resp['outputs']))
    unspent_list: list
    try:
        proxy = Proxy(service_url=plugin.service_url)
        unspent_list = proxy.call('listunspent', 0, 100)
    except Exception as e:
        plugin.log(f'Exception {str(e)}', 'error')
        return { 'code': -1, 'message': 'Could not connect to bitcoind.' }

    new_unspent = list(filter(lambda unspent: unspent['txid'] not in txids, unspent_list))
    for unspent in new_unspent:
        amount = round(unspent['amount'] * Decimal(1e8))
        output = {
            'txid': unspent['txid'],
            'output': unspent['vout'],
            'value': amount,
            'amount_msat': str(amount) + '000msat',
            'scriptpubkey': unspent['scriptPubKey'],
            'address': unspent['address'],
            'status': 'unconfirmed',
            'reserved': 'false'
        }
        listfunds_resp['outputs'].insert(0, output)
    return listfunds_resp

plugin.add_option(
    'listmempoolfunds-rpchost',
    '127.0.0.1',
    'bitcoind RPC host',
    'string'
)
plugin.add_option(
    'listmempoolfunds-rpcport',
    None,
    'bitcoind RPC port (inferred by network if not supplied)',
    'string'
)
plugin.add_option(
    'listmempoolfunds-rpcuser',
    'user',
    'bitcoind RPC user',
    'string'
)
plugin.add_option(
    'listmempoolfunds-rpcpassword',
    'passwd',
    'bitcoind RPC password',
    'string'
)
plugin.add_option(
    'listmempoolfunds-descriptor',
    None,
    'Wallet descriptor used for receiving and change. '
    'Retrieved using dumponchaindescriptors via the hsmtool.'
    'Must have both descriptors included as separate options.',
    'string',
    False,
    True
)

plugin.run()
