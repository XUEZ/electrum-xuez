import base64
import unittest
import sys
from ecdsa.util import number_to_string

from lib.bitcoin import (
    generator_secp256k1, point_to_ser, public_key_to_p2pkh, EC_KEY,
    bip32_root, bip32_public_derivation, bip32_private_derivation, pw_encode,
    pw_decode, Hash, public_key_from_private_key, address_from_private_key,
    is_address, is_private_key, xpub_from_xprv, is_new_seed, is_old_seed,
    var_int, op_push, address_to_script, regenerate_key,
    verify_message, deserialize_privkey, serialize_privkey,
    is_b58_address, address_to_scripthash, is_minikey, is_compressed, is_xpub,
    xpub_type, is_xprv, is_bip32_derivation, seed_type, NetworkConstants,
    deserialize_xprv, deserialize_xpub, deserialize_drkv, deserialize_drkp)
from lib.util import bfh, bh2u
from lib.keystore import from_master_key

try:
    import ecdsa
except ImportError:
    sys.exit("Error: python-ecdsa does not seem to be installed. Try 'sudo pip install ecdsa'")


class Test_bitcoin(unittest.TestCase):

    def test_crypto(self):
        for message in [b"Chancellor on brink of second bailout for banks", b'\xff'*512]:
            self._do_test_crypto(message)

    def _do_test_crypto(self, message):
        G = generator_secp256k1
        _r  = G.order()
        pvk = ecdsa.util.randrange( pow(2,256) ) %_r

        Pub = pvk*G
        pubkey_c = point_to_ser(Pub,True)
        #pubkey_u = point_to_ser(Pub,False)
        addr_c = public_key_to_p2pkh(pubkey_c)

        #print "Private key            ", '%064x'%pvk
        eck = EC_KEY(number_to_string(pvk,_r))

        #print "Compressed public key  ", pubkey_c.encode('hex')
        enc = EC_KEY.encrypt_message(message, pubkey_c)
        dec = eck.decrypt_message(enc)
        self.assertEqual(message, dec)

        #print "Uncompressed public key", pubkey_u.encode('hex')
        #enc2 = EC_KEY.encrypt_message(message, pubkey_u)
        dec2 = eck.decrypt_message(enc)
        self.assertEqual(message, dec2)

        signature = eck.sign_message(message, True)
        #print signature
        EC_KEY.verify_message(eck, signature, message)

    def test_msg_signing(self):
        msg1 = b'Chancellor on brink of second bailout for banks'
        msg2 = b'Electrum'

        def sign_message_with_wif_privkey(wif_privkey, msg):
            txin_type, privkey, compressed = deserialize_privkey(wif_privkey)
            key = regenerate_key(privkey)
            return key.sign_message(msg, compressed)

        sig1 = sign_message_with_wif_privkey(
            'YV56icVrjNioXn9kpZeL3DvtC7aN7kt8tr5ur2wqpMaXeJ3YQirG', msg1)
        addr1 = 'XJtSNWxWufU5XAh59JfXPx9peodJwTqPqf'
        sig2 = sign_message_with_wif_privkey(
            'YQ6GbE34bXDgMgJEEJ87Buri6MCCcCNZoozpc34ima1PBjKqA8fj', msg2)
        addr2 = 'XMy7W6qnXjKQzjKCD4JpkNBccMXwqQdGjn'

        sig1_b64 = base64.b64encode(sig1)
        sig2_b64 = base64.b64encode(sig2)

        self.assertEqual(sig1_b64, b'H/VkUdJ1QTZHgBtJGamJPdGEL1+/q1414mU49O9pGdEhQzUhnAH5zb2bRrAzptQmbcD1fgUG7JOf4HU4VCES+5M=')
        self.assertEqual(sig2_b64, b'IFV7liH2eU5SP47M0QDlIAuUxfWGEpOvrpbZq9Guto0NZAurCMVC7qXcUHLRGsfXRHgLGkRm64WTmFJhhRvfqV8=')

        self.assertTrue(verify_message(addr1, sig1, msg1))
        self.assertTrue(verify_message(addr2, sig2, msg2))

        self.assertFalse(verify_message(addr1, b'wrong', msg1))
        self.assertFalse(verify_message(addr1, sig2, msg1))

    def test_aes_homomorphic(self):
        """Make sure AES is homomorphic."""
        payload = u'\u66f4\u7a33\u5b9a\u7684\u4ea4\u6613\u5e73\u53f0'
        password = u'secret'
        enc = pw_encode(payload, password)
        dec = pw_decode(enc, password)
        self.assertEqual(dec, payload)

    def test_aes_encode_without_password(self):
        """When not passed a password, pw_encode is noop on the payload."""
        payload = u'\u66f4\u7a33\u5b9a\u7684\u4ea4\u6613\u5e73\u53f0'
        enc = pw_encode(payload, None)
        self.assertEqual(payload, enc)

    def test_aes_deencode_without_password(self):
        """When not passed a password, pw_decode is noop on the payload."""
        payload = u'\u66f4\u7a33\u5b9a\u7684\u4ea4\u6613\u5e73\u53f0'
        enc = pw_decode(payload, None)
        self.assertEqual(payload, enc)

    def test_aes_decode_with_invalid_password(self):
        """pw_decode raises an Exception when supplied an invalid password."""
        payload = u"blah"
        password = u"uber secret"
        wrong_password = u"not the password"
        enc = pw_encode(payload, password)
        self.assertRaises(Exception, pw_decode, enc, wrong_password)

    def test_hash(self):
        """Make sure the Hash function does sha256 twice"""
        payload = u"test"
        expected = b'\x95MZI\xfdp\xd9\xb8\xbc\xdb5\xd2R&x)\x95\x7f~\xf7\xfalt\xf8\x84\x19\xbd\xc5\xe8"\t\xf4'

        result = Hash(payload)
        self.assertEqual(expected, result)

    def test_var_int(self):
        for i in range(0xfd):
            self.assertEqual(var_int(i), "{:02x}".format(i) )

        self.assertEqual(var_int(0xfd), "fdfd00")
        self.assertEqual(var_int(0xfe), "fdfe00")
        self.assertEqual(var_int(0xff), "fdff00")
        self.assertEqual(var_int(0x1234), "fd3412")
        self.assertEqual(var_int(0xffff), "fdffff")
        self.assertEqual(var_int(0x10000), "fe00000100")
        self.assertEqual(var_int(0x12345678), "fe78563412")
        self.assertEqual(var_int(0xffffffff), "feffffffff")
        self.assertEqual(var_int(0x100000000), "ff0000000001000000")
        self.assertEqual(var_int(0x0123456789abcdef), "ffefcdab8967452301")

    def test_op_push(self):
        self.assertEqual(op_push(0x00), '00')
        self.assertEqual(op_push(0x12), '12')
        self.assertEqual(op_push(0x4b), '4b')
        self.assertEqual(op_push(0x4c), '4c4c')
        self.assertEqual(op_push(0xfe), '4cfe')
        self.assertEqual(op_push(0xff), '4dff00')
        self.assertEqual(op_push(0x100), '4d0001')
        self.assertEqual(op_push(0x1234), '4d3412')
        self.assertEqual(op_push(0xfffe), '4dfeff')
        self.assertEqual(op_push(0xffff), '4effff0000')
        self.assertEqual(op_push(0x10000), '4e00000100')
        self.assertEqual(op_push(0x12345678), '4e78563412')

    def test_address_to_script(self):
        # base58 P2PKH
        self.assertEqual(address_to_script('XJtSNWxWufU5XAh59JfXPx9peodJwTqPqf'), '76a91452af650fba3ebae076e81e3475045c1733e1933d88ac')
        self.assertEqual(address_to_script('XMy7W6qnXjKQzjKCD4JpkNBccMXwqQdGjn'), '76a914747a19c67e086c3426821cd4bfd011e44e5a8e8788ac')

        # base58 P2SH
        self.assertEqual(address_to_script('8WHUEVtMDLeereT5r4ZoNKjr3MXr4gqfon'), 'a914a6bc1aa409ab5f2e895aa28f3cadb30dc623728e87')
        self.assertEqual(address_to_script('8WhNpVKta6kkbP24HfvvQVeHEmgBQYiJCB'), 'a914ab41915b8462a3a12e1d7a2b8fd84c06ddeb9dfb87')


class Test_bitcoin_testnet(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        NetworkConstants.set_testnet()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        NetworkConstants.set_mainnet()

    def test_address_to_script(self):
        # base58 P2PKH
        self.assertEqual(address_to_script('yah2ARXMnY5A9VaR5Cd43fjiQnsu2vZ5a8'), '76a9149da64e300c5e4eb4aaffc9c2fd465348d5618ad488ac')
        self.assertEqual(address_to_script('yPeP8a774GuYaZyqJPxC7K24hcbcsqz1Au'), '76a914247d2d5b6334bdfa2038e85b20fc15264f8e5d2788ac')

        # base58 P2SH
        self.assertEqual(address_to_script('8pWgedHiF9DQswwXdR59ATSQe9pxyBZqbv'), 'a9146eae23d8c4a941316017946fc761a7a6c85561fb87')
        self.assertEqual(address_to_script('91EoMZCG6Yfs9NGZLYQcrJcUa55TLnvVxz'), 'a914e4567743d378957cd2ee7072da74b1203c1a7a0b87')


class Test_xprv_xpub(unittest.TestCase):

    xprv_xpub = (
        # Taken from test vectors in https://en.bitcoin.it/wiki/BIP_0032_TestVectors
        {'xprv': 'TDt9EZSrSEZyJVGtRKog7FzuoLao9aHdKRGfjqFKzXcs1tpeBJGNqMmP2PUrnyLHLUeykytcPuchZUNneTZJMTS9ndsWpka56fiz6pkRRSQnTkR',
         'xpub': 'ToEA6qpu6F7tMbkhs81LYpv1AE65hGb34J2DRjTXZ9gS22UVDP3KTZrBmjkFJsESg8gkUSvb21c1aR6y14XQCjmKWrFmzrkMhANJqxP3GenZSJd',
         'xtype': 'standard'},
    )

    def _do_test_bip32(self, seed, sequence):
        xprv, xpub = bip32_root(bfh(seed), 'standard')
        self.assertEqual("m/", sequence[0:2])
        path = 'm'
        sequence = sequence[2:]
        for n in sequence.split('/'):
            child_path = path + '/' + n
            if n[-1] != "'":
                xpub2 = bip32_public_derivation(xpub, path, child_path)
            xprv, xpub = bip32_private_derivation(xprv, path, child_path)
            if n[-1] != "'":
                self.assertEqual(xpub, xpub2)
            path = child_path

        return xpub, xprv

    def test_bip32(self):
        # see https://en.bitcoin.it/wiki/BIP_0032_TestVectors
        xpub, xprv = self._do_test_bip32("000102030405060708090a0b0c0d0e0f", "m/0'/1/2'/2/1000000000")
        self.assertEqual("ToEA6qpu6F7tMbkhs81LYpv1AE65hGb34J2DRjTXZ9gS22UVDP3KTZrBmjkFJsESg8gkUSvb21c1aR6y14XQCjmKWrFmzrkMhANJqxP3GenZSJd", xpub)
        self.assertEqual("TDt9EZSrSEZyJVGtRKog7FzuoLao9aHdKRGfjqFKzXcs1tpeBJGNqMmP2PUrnyLHLUeykytcPuchZUNneTZJMTS9ndsWpka56fiz6pkRRSQnTkR", xprv)

        xpub, xprv = self._do_test_bip32("fffcf9f6f3f0edeae7e4e1dedbd8d5d2cfccc9c6c3c0bdbab7b4b1aeaba8a5a29f9c999693908d8a8784817e7b7875726f6c696663605d5a5754514e4b484542","m/0/2147483647'/1/2147483646'/2")
        self.assertEqual("xpub6FnCn6nSzZAw5Tw7cgR9bi15UV96gLZhjDstkXXxvCLsUXBGXPdSnLFbdpq8p9HmGsApME5hQTZ3emM2rnY5agb9rXpVGyy3bdW6EEgAtqt", xpub)
        self.assertEqual("xprvA2nrNbFZABcdryreWet9Ea4LvTJcGsqrMzxHx98MMrotbir7yrKCEXw7nadnHM8Dq38EGfSh6dqA9QWTyefMLEcBYJUuekgW4BYPJcr9E7j", xprv)

    def test_xpub_from_xprv(self):
        """We can derive the xpub key from a xprv."""
        for xprv_details in self.xprv_xpub:
            result = xpub_from_xprv(xprv_details['xprv'])
            self.assertEqual(result, xprv_details['xpub'])

    def test_is_xpub(self):
        for xprv_details in self.xprv_xpub:
            xpub = xprv_details['xpub']
            self.assertTrue(is_xpub(xpub))
        self.assertFalse(is_xpub('xpub1nval1d'))
        self.assertFalse(is_xpub('xpub661MyMwAqRbcFWohJWt7PHsFEJfZAvw9ZxwQoDa4SoMgsDDM1T7WK3u9E4edkC4ugRnZ8E4xDZRpk8Rnts3Nbt97dPwT52WRONGBADWRONG'))

    def test_xpub_type(self):
        for xprv_details in self.xprv_xpub:
            xpub = xprv_details['xpub']
            self.assertEqual(xprv_details['xtype'], xpub_type(xpub))

    def test_is_xprv(self):
        for xprv_details in self.xprv_xpub:
            xprv = xprv_details['xprv']
            self.assertTrue(is_xprv(xprv))
        self.assertFalse(is_xprv('xprv1nval1d'))
        self.assertFalse(is_xprv('xprv661MyMwAqRbcFWohJWt7PHsFEJfZAvw9ZxwQoDa4SoMgsDDM1T7WK3u9E4edkC4ugRnZ8E4xDZRpk8Rnts3Nbt97dPwT52WRONGBADWRONG'))

    def test_is_bip32_derivation(self):
        self.assertTrue(is_bip32_derivation("m/0'/1"))
        self.assertTrue(is_bip32_derivation("m/0'/0'"))
        self.assertTrue(is_bip32_derivation("m/44'/225'/0'/0/0"))
        self.assertTrue(is_bip32_derivation("m/44'/225'/0'/0/0"))
        self.assertFalse(is_bip32_derivation("mmmmmm"))
        self.assertFalse(is_bip32_derivation("n/"))
        self.assertFalse(is_bip32_derivation(""))
        self.assertFalse(is_bip32_derivation("m/q8462"))


class Test_drk_import(unittest.TestCase):
    """ The keys used in this class are TEST keys from
        https://en.bitcoin.it/wiki/BIP_0032_TestVectors"""

    xpub = 'ToEA6ij48MPyPqZFPKUuaP3iqKHBWU9f97gBPqtXv9WBwKSn2nwXPomtuwLLmwipDzVghkWisV2GAZhEqCRXc9FBijvWxB7yap1gTzmSp65t87m'
    xprv = 'TDt9EapLfhkwakQMYqiaME1AzA41fYs6HZFxUWp8tSkLHUiovTvsguxHykeiimKJUR7WTs5Z7YY7kUBeWmjR3UYc7VT5Pd6gvQKeL7zQdRNc3Tt'
    drkp = 'drkpRv3MKBiuEwFtNSzj62Kwpj7Cd77NVUYAPoxBN8EL5rSn6EMWr3bD4RnwwbGrnQZStpYJ1iGZCiGKt9mR7aYNtaurGyTCQZuwVzqzAbX9znj'
    drkv = 'drkvjLuVs1zJu2rKwexyhS5mYeVuNs2umm4bZMg8hv4Zy28xLX2tXbr6tzytFNsAsqjveLoFqSgcNhF4YoonH1y35REUMeSFJZ8ALdoFutwvbtw'
    master_fpr = '126fe05a'
    sec_key = 'ebf0405dc620034fb0ef3eb00e83ca8e28314b8e22a3a06dc4e19e6f272a1e83'
    pub_key = '038908c4bf9bc7ba596ba88dfb2594ec22c95d866d19f4c8926827beee3c8795e5'
    child_num = '00000001'
    chain_code = '20976ef740cddc7ae060121088567c940a4ef34cc690c67ab9f1bf9e8a4d5320'
    xtype = 'standard'

    def check_deserialized(self, deserialized, prv):
        xtype, depth, fpr, child_number, c, K = deserialized

        self.assertEqual(self.xtype, xtype)
        self.assertEqual(1, depth)
        self.assertEqual(self.master_fpr, bh2u(fpr))
        self.assertEqual(self.child_num, bh2u(child_number))
        self.assertEqual(self.chain_code, bh2u(c))
        if prv:
            self.assertEqual(self.sec_key, bh2u(K))
        else:
            self.assertEqual(self.pub_key, bh2u(K))

    def test_deserialize_xpub(self):
        self.check_deserialized(deserialize_xpub(self.xpub), False)

    def test_deserialize_xprv(self):
        self.check_deserialized(deserialize_xprv(self.xprv), True)

    def test_deserialize_drkp(self):
        self.check_deserialized(deserialize_drkp(self.drkp), False)

    def test_deserialize_drkv(self):
        self.check_deserialized(deserialize_drkv(self.drkv), True)

    def test_keystore_from_xpub(self):
        keystore = from_master_key(self.xpub)
        self.assertEqual(keystore.xpub, self.xpub)
        self.assertEqual(keystore.xprv, None)

    def test_keystore_from_xprv(self):
        keystore = from_master_key(self.xprv)
        self.assertEqual(keystore.xpub, self.xpub)
        self.assertEqual(keystore.xprv, self.xprv)

    def test_keystore_from_drkp(self):
        keystore = from_master_key(self.drkp)
        self.assertEqual(keystore.xpub, self.xpub)
        self.assertEqual(keystore.xprv, None)

    def test_keystore_from_drkv(self):
        keystore = from_master_key(self.drkv)
        self.assertEqual(keystore.xpub, self.xpub)
        self.assertEqual(keystore.xprv, self.xprv)


class Test_keyImport(unittest.TestCase):

    priv_pub_addr = (
           {'priv': 'YV56icVrjNioXn9kpZeL3DvtC7aN7kt8tr5ur2wqpMaXeJ3YQirG',
            'pub': '02c59b76fabcfc146c75365da6475f33d8fa596ef76b4b301d66da74180c429c78',
            'address': 'XJtSNWxWufU5XAh59JfXPx9peodJwTqPqf',
            'minikey' : False,
            'txin_type': 'p2pkh',
            'compressed': True,
            'addr_encoding': 'base58',
            'scripthash': '557041e6ceca2cff492d60f035ae3db4408ae6aa50840d932b95858b772f6133'},
           {'priv': 'YQ6GbE34bXDgMgJEEJ87Buri6MCCcCNZoozpc34ima1PBjKqA8fj',
            'pub': '03fa334250ddb2a51b30b31a98922a5e1c107042a482b68fc74999c6962ae3276e',
            'address': 'XMy7W6qnXjKQzjKCD4JpkNBccMXwqQdGjn',
            'minikey': False,
            'txin_type': 'p2pkh',
            'compressed': False,
            'addr_encoding': 'base58',
            'scripthash': 'f5914651408417e1166f725a5829ff9576d0dbf05237055bf13abd2af7f79473'},
           # from http://bitscan.com/articles/security/spotlight-on-mini-private-keys
           {'priv': 'SzavMBLoXU6kDrqtUVmffv',
            'pub': '02588d202afcc1ee4ab5254c7847ec25b9a135bbda0f2bc69ee1a714749fd77dc9',
            'address': 'XixkkUaFKBmj5mieoLRNXTUiXhCmM87ZSj',
            'minikey': True,
            'txin_type': 'p2pkh',
            'compressed': True,  # this is actually ambiguous... issue #2748
            'addr_encoding': 'base58',
            'scripthash': '60ad5a8b922f758cd7884403e90ee7e6f093f8d21a0ff24c9a865e695ccefdf1'},
    )

    def test_public_key_from_private_key(self):
        for priv_details in self.priv_pub_addr:
            txin_type, privkey, compressed = deserialize_privkey(priv_details['priv'])
            result = public_key_from_private_key(privkey, compressed)
            self.assertEqual(priv_details['pub'], result)
            self.assertEqual(priv_details['txin_type'], txin_type)
            self.assertEqual(priv_details['compressed'], compressed)

    def test_address_from_private_key(self):
        for priv_details in self.priv_pub_addr:
            addr2 = address_from_private_key(priv_details['priv'])
            self.assertEqual(priv_details['address'], addr2)

    def test_is_valid_address(self):
        for priv_details in self.priv_pub_addr:
            addr = priv_details['address']
            self.assertFalse(is_address(priv_details['priv']))
            self.assertFalse(is_address(priv_details['pub']))
            self.assertTrue(is_address(addr))

            is_enc_b58 = priv_details['addr_encoding'] == 'base58'
            self.assertEqual(is_enc_b58, is_b58_address(addr))

        self.assertFalse(is_address("not an address"))

    def test_is_private_key(self):
        for priv_details in self.priv_pub_addr:
            self.assertTrue(is_private_key(priv_details['priv']))
            self.assertFalse(is_private_key(priv_details['pub']))
            self.assertFalse(is_private_key(priv_details['address']))
        self.assertFalse(is_private_key("not a privkey"))

    def test_serialize_privkey(self):
        for priv_details in self.priv_pub_addr:
            txin_type, privkey, compressed = deserialize_privkey(priv_details['priv'])
            priv2 = serialize_privkey(privkey, compressed, txin_type)
            if not priv_details['minikey']:
                self.assertEqual(priv_details['priv'], priv2)

    def test_address_to_scripthash(self):
        for priv_details in self.priv_pub_addr:
            sh = address_to_scripthash(priv_details['address'])
            self.assertEqual(priv_details['scripthash'], sh)

    def test_is_minikey(self):
        for priv_details in self.priv_pub_addr:
            minikey = priv_details['minikey']
            priv = priv_details['priv']
            self.assertEqual(minikey, is_minikey(priv))

    def test_is_compressed(self):
        for priv_details in self.priv_pub_addr:
            self.assertEqual(priv_details['compressed'],
                             is_compressed(priv_details['priv']))


class Test_seeds(unittest.TestCase):
    """ Test old and new seeds. """

    mnemonics = {
        ('cell dumb heartbeat north boom tease ship baby bright kingdom rare squeeze', 'old'),
        ('cell dumb heartbeat north boom tease ' * 4, 'old'),
        ('cell dumb heartbeat north boom tease ship baby bright kingdom rare badword', ''),
        ('cElL DuMb hEaRtBeAt nOrTh bOoM TeAsE ShIp bAbY BrIgHt kInGdOm rArE SqUeEzE', 'old'),
        ('   cElL  DuMb hEaRtBeAt nOrTh bOoM  TeAsE ShIp    bAbY BrIgHt kInGdOm rArE SqUeEzE   ', 'old'),
        # below seed is actually 'invalid old' as it maps to 33 hex chars
        ('hurry idiot prefer sunset mention mist jaw inhale impossible kingdom rare squeeze', 'old'),
        ('cram swing cover prefer miss modify ritual silly deliver chunk behind inform able', 'standard'),
        ('cram swing cover prefer miss modify ritual silly deliver chunk behind inform', ''),
        ('ostrich security deer aunt climb inner alpha arm mutual marble solid task', 'standard'),
        ('OSTRICH SECURITY DEER AUNT CLIMB INNER ALPHA ARM MUTUAL MARBLE SOLID TASK', 'standard'),
        ('   oStRiCh sEcUrItY DeEr aUnT ClImB       InNeR AlPhA ArM MuTuAl mArBlE   SoLiD TaSk  ', 'standard'),
        ('x8', 'standard'),
        ('science dawn member doll dutch real ca brick knife deny drive list', ''),
    }
    
    def test_new_seed(self):
        seed = "cram swing cover prefer miss modify ritual silly deliver chunk behind inform able"
        self.assertTrue(is_new_seed(seed))

        seed = "cram swing cover prefer miss modify ritual silly deliver chunk behind inform"
        self.assertFalse(is_new_seed(seed))

    def test_old_seed(self):
        self.assertTrue(is_old_seed(" ".join(["like"] * 12)))
        self.assertFalse(is_old_seed(" ".join(["like"] * 18)))
        self.assertTrue(is_old_seed(" ".join(["like"] * 24)))
        self.assertFalse(is_old_seed("not a seed"))

        self.assertTrue(is_old_seed("0123456789ABCDEF" * 2))
        self.assertTrue(is_old_seed("0123456789ABCDEF" * 4))

    def test_seed_type(self):
        for seed_words, _type in self.mnemonics:
            self.assertEqual(_type, seed_type(seed_words), msg=seed_words)
