# listmempoolfunds

This plugin adds the ability to track unconfirmed wallet deposits. It introduces
a new method `listmempoolfunds` that has the same signature and response format
as `listfunds`, except it will also return unconfirmed received outputs.

## How does listmempoolfunds work

It leverages Bitcoin Core's watchonly descriptor wallet and clightning's
hsmtool. By creating a new descriptor wallet and importing the node's xpubs,
Bitcoin Core will track all incoming payments. Since bitcoind handles tracking
the payments in the mempool, the plugin can query bitcoind for any new payments
that aren't present in `listfunds`. These new payments can be appended to the
`listfunds` response and returned, and it appears just like `listfunds` is
tracking unconfirmed deposits!

## Dependencies

This plugin depends on having RPC access to a running Bitcoin Core v0.21.0 or
higher. It also needs the descriptor wallet compiled in and not disabled
(`disablewallet=0`), and it needs to not be running in blocks-only mode
(`blocksonly=0`).
It *can* be running in pruned mode (`prune=<n>`), but you will need to have
blocks back to at least where the first deposit to the node was made. After it
has imported the descriptors and rescanned, older blocks can be pruned.

## Installation

Run `pip3 install --user -r -requirements.txt` and include the
`listmempoolfunds.py` file as a plugin via instructions [here](https://github.com/lightningd/plugins/#installation).

Set the `listmempoolfunds-rpcuser` and `listmempoolfunds-rpcpassword` options to
the credentials of your bitcoind instance.
You must also set the `listmempoolfunds-descriptor` option twice in order to
import the proper descriptors. If you are using the default locations, this can
be done with the following command:
```
$ ./tools/hsmtool dumponchaindescriptors ~/.lightning/bitcoin/hsm_secret | xargs -n1 printf "listmempoolfunds-descriptor=%s\n" >> ~/.lightning/config
```

On startup, the plugin will check if the wallet exists and if it is loaded. If
not, it will create the wallet, import the descriptors, and perform a rescan.
On mainnet the rescan can take several hours, but will only happen the first time.
