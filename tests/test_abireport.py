import unittest
import abireport


def mock_return(retval):
    """
    Simple mock method to set return value of a function
    """
    def mock_fn(_):
        return retval

    return mock_fn


class TestAbireport(unittest.TestCase):

    def test_get_soname(self):
        """
        Test get_soname function with valid get_output results
        """
        backup = abireport.get_output
        abireport.get_output = mock_return('SONAME               libtest.so.14')
        self.assertEqual(abireport.get_soname('test'), 'libtest.so.14')
        abireport.get_output = backup

    def test_get_soname_none(self):
        """
        Test get_soname function with no get_output results
        """
        backup = abireport.get_output
        abireport.get_output = mock_return('')
        self.assertEqual(abireport.get_soname('test'), None)
        abireport.get_output = backup

    def test_get_soname_error(self):
        """
        Test get_soname function with exception raised in get_output
        """
        backup = abireport.get_output

        def mock_get_output(cmd):
            raise Exception('testing exception')

        abireport.get_output = mock_get_output
        self.assertEqual(abireport.get_soname('test'), None)
        abireport.get_output = backup

    def test_get_shared_dependencies(self):
        """
        Test get_shared_dependencies function with valid get_output results
        """
        backup = abireport.get_output
        abireport.get_output = mock_return(READELF1)
        results = set(['libdl.so.2', 'libz.so.1', 'libexpat.so.1',
                       'libstdc++.so.6', 'libm.so.6', 'libgcc_s.so.1',
                       'libc.so.6'])
        self.assertEqual(abireport.get_shared_dependencies('test'), results)
        abireport.get_output = backup

    def test_get_shared_dependencies_none(self):
        """
        Test get_shared_dependencies with no matches
        """
        backup = abireport.get_output
        abireport.get_output = mock_return(READELF2)
        self.assertEqual(abireport.get_shared_dependencies('test'), set())
        abireport.get_output = backup

    def test_is_dynamic_binary(self):
        """
        Test is_dynamic_binary function for True return
        """
        backup_isfile = abireport.os.path.isfile
        backup_exists = abireport.os.path.exists
        backup_get_file_magic = abireport.get_file_magic

        abireport.os.path.isfile = mock_return(True)
        abireport.os.path.exists = mock_return(True)
        abireport.get_file_magic = mock_return(FILEMAGIC1)

        self.assertTrue(abireport.is_dynamic_binary('test'))

        abireport.os.path.isfile = backup_isfile
        abireport.os.path.exists = backup_exists
        abireport.get_file_magic = backup_get_file_magic

    def test_is_dynamic_binary_false(self):
        """
        Test is_dynamic_binary function for False return
        """
        backup_exists = abireport.os.path.exists
        backup_isfile = abireport.os.path.isfile
        backup_get_file_magic = abireport.get_file_magic

        abireport.os.path.exists = mock_return(True)
        abireport.os.path.isfile = mock_return(True)
        abireport.get_file_magic = mock_return('This is not a matched string')

        self.assertFalse(abireport.is_dynamic_binary('test'))

        abireport.os.path.exists = backup_exists
        abireport.os.path.isfile = backup_isfile
        abireport.get_file_magic = backup_get_file_magic

    def test_is_file_valid(self):
        """
        Test is_file_valid function with valid file magic
        """
        backup_exists = abireport.os.path.exists
        backup_islink = abireport.os.path.islink
        backup_get_file_magic = abireport.get_file_magic

        abireport.os.path.exists = mock_return(True)
        abireport.os.path.islink = mock_return(False)
        abireport.get_file_magic = mock_return(FILEMAGIC1)

        self.assertTrue(abireport.is_file_valid('test'))

        abireport.os.path.exists = backup_exists
        abireport.os.path.islink= backup_islink
        abireport.get_file_magic = backup_get_file_magic

    def test_is_file_valid_false(self):
        """
        Test is_file_valid function with valid file magic
        """
        backup_exists = abireport.os.path.exists
        backup_islink = abireport.os.path.islink
        backup_get_file_magic = abireport.get_file_magic

        abireport.os.path.exists = mock_return(True)
        abireport.os.path.islink = mock_return(False)
        abireport.get_file_magic = mock_return('This is not a matched string')

        self.assertFalse(abireport.is_file_valid('test'))

        abireport.os.path.exists = backup_exists
        abireport.os.path.islink= backup_islink
        abireport.get_file_magic = backup_get_file_magic

    def test_dump_symbols(self):
        """
        Test dump_symbols function with valid nm output
        """
        backup = abireport.get_output
        abireport.get_output = mock_return(NM1)
        results = set(['WXMPIterator_DecrementRefCount_1',
                       'WXMPIterator_IncrementRefCount_1',
                       '_Z13XMP_InitMutexP15pthread_mutex_t',
                       '_Z13XMP_TermMutexR15pthread_mutex_t',
                       '_Z14CloneOffspringPK8XMP_NodePS_',
                       '_Z14SortNamedNodesRSt6vectorIP8XMP_NodeSaIS1_EE',
                       '_Z15CompareSubtreesRK8XMP_NodeS1_',
                       '_ZN5Exiv211focalLengthERKNS_8ExifDataE',
                       '_ZN5Exiv211getRationalEPKhNS_9ByteOrderE',
                       '_ZN5Exiv211isBigEndianEv',
                       '_ZN5Exiv211orientationERKNS_8ExifDataE',
                       '_ZN5Exiv28GifImageC2ESt8auto_ptrINS_7BasicIoEE'])
        self.assertEqual(abireport.dump_symbols('test'), results)
        abireport.get_output = backup

    def test_dump_symbols_exit(self):
        """
        Test dump_symbols function with fatal exception
        """
        backup = abireport.get_output

        def mock_get_output(_):
            raise Exception('This is a test exception')

        abireport.get_output = mock_get_output
        with self.assertRaises(SystemExit) as dumpsymbols:
            abireport.dump_symbols('test')

        self.assertEqual(dumpsymbols.exception.code, 1)


READELF1 = """

Dynamic section at offset 0x2d0788 contains 31 entries:
  Tag        Type                         Name/Value
 0x0000000000000001 (NEEDED)             Shared library: [libdl.so.2]
 0x0000000000000001 (NEEDED)             Shared library: [libz.so.1]
 0x0000000000000001 (NEEDED)             Shared library: [libexpat.so.1]
 0x0000000000000001 (NEEDED)             Shared library: [libstdc++.so.6]
 0x0000000000000001 (NEEDED)             Shared library: [libm.so.6]
 0x0000000000000001 (NEEDED)             Shared library: [libgcc_s.so.1]
 0x0000000000000001 (NEEDED)             Shared library: [libc.so.6]
 0x000000000000000e (SONAME)             Library soname: [libexiv2.so.14]
 0x000000000000000f (RPATH)              Library rpath: [/usr/lib]
 0x000000000000000c (INIT)               0xca320
 0x000000000000000d (FINI)               0x20e6cc
 0x0000000000000019 (INIT_ARRAY)         0x2a5a70
 0x000000000000001b (INIT_ARRAYSZ)       400 (bytes)
 0x000000000000001a (FINI_ARRAY)         0x2a5c00
 0x000000000000001c (FINI_ARRAYSZ)       8 (bytes)
 0x0000000000000004 (HASH)               0x1f0
 0x0000000000000005 (STRTAB)             0x23f10
 0x0000000000000006 (SYMTAB)             0x8ac0
 0x000000000000000a (STRSZ)              252569 (bytes)
 0x000000000000000b (SYMENT)             24 (bytes)
 0x0000000000000003 (PLTGOT)             0x2d19b8
 0x0000000000000007 (RELA)               0x63f48
 0x0000000000000008 (RELASZ)             418776 (bytes)
 0x0000000000000009 (RELAENT)            24 (bytes)
 0x0000000000000018 (BIND_NOW)           
 0x000000006ffffffb (FLAGS_1)            Flags: NOW
 0x000000006ffffffe (VERNEED)            0x63e08
 0x000000006fffffff (VERNEEDNUM)         5
 0x000000006ffffff0 (VERSYM)             0x619aa
 0x000000006ffffff9 (RELACOUNT)          11626
 0x0000000000000000 (NULL)               0x0
"""

READELF2 = """

Dynamic section at offset 0x2d0788 contains 31 entries:
  Tag        Type                         Name/Value
 0x000000000000000e (SONAME)             Library soname: [libexiv2.so.14]
 0x000000000000000f (RPATH)              Library rpath: [/usr/lib]
 0x000000000000000c (INIT)               0xca320
 0x000000000000000d (FINI)               0x20e6cc
 0x0000000000000019 (INIT_ARRAY)         0x2a5a70
 0x000000000000001b (INIT_ARRAYSZ)       400 (bytes)
 0x000000000000001a (FINI_ARRAY)         0x2a5c00
 0x000000000000001c (FINI_ARRAYSZ)       8 (bytes)
 0x0000000000000004 (HASH)               0x1f0
 0x0000000000000005 (STRTAB)             0x23f10
 0x0000000000000006 (SYMTAB)             0x8ac0
 0x000000000000000a (STRSZ)              252569 (bytes)
 0x000000000000000b (SYMENT)             24 (bytes)
 0x0000000000000003 (PLTGOT)             0x2d19b8
 0x0000000000000007 (RELA)               0x63f48
 0x0000000000000008 (RELASZ)             418776 (bytes)
 0x0000000000000009 (RELAENT)            24 (bytes)
 0x0000000000000018 (BIND_NOW)           
 0x000000006ffffffb (FLAGS_1)            Flags: NOW
 0x000000006ffffffe (VERNEED)            0x63e08
 0x000000006fffffff (VERNEEDNUM)         5
 0x000000006ffffff0 (VERSYM)             0x619aa
 0x000000006ffffff9 (RELACOUNT)          11626
 0x0000000000000000 (NULL)               0x0
"""

FILEMAGIC1 = '/path/to/so/libtest.so.1: ELF 64-bit LSB shared object, ' \
             'x86-64, version 1 (SYSV), dynamically linked, '           \
             'BuildID[sha1]=c99853fe0c5d8f3c7550848edf25fe7782fb22c3, stripped'

NM1 = """
00000000002f1d88 B voidStringPtr
00000000002f1d90 B voidVoidPtr
00000000002f1ce0 B void_wResult
00000000001d1a40 T WXMPIterator_DecrementRefCount_1
00000000001d19f0 T WXMPIterator_IncrementRefCount_1
00000000001daa80 T _Z13XMP_InitMutexP15pthread_mutex_t
00000000001daaa0 T _Z13XMP_TermMutexR15pthread_mutex_t
00000000001db900 T _Z14CloneOffspringPK8XMP_NodePS_
00000000001df4e0 A _Z14SortNamedNodesRSt6vectorIP8XMP_NodeSaIS1_EE
00000000001dc450 T _Z15CompareSubtreesRK8XMP_NodeS1_
000000000011d260 A _ZN5Exiv211focalLengthERKNS_8ExifDataE
00000000001b0510 T _ZN5Exiv211getRationalEPKhNS_9ByteOrderE
0000000000197160 T _ZN5Exiv211isBigEndianEv
000000000011c8e0 T _ZN5Exiv211orientationERKNS_8ExifDataE
00000000002c7000 D _ZN5Exiv211sectionInfoE
00000000002c45e0 D _ZN5Exiv212xmpXmpBJInfoE
0000000000137660 T _ZN5Exiv28GifImageC2ESt8auto_ptrINS_7BasicIoEE
00000000002658d8 R _ZN5Exiv28Internal10canonCfCfgE
0000000000265960 R _ZN5Exiv28Internal10canonCsCfgE
00000000002ebac0 B _ZN5Exiv28Internal14SigmaMakerNote8tagInfo_E
"""

if __name__ == '__main__':
    unittest.main(buffer=True)
