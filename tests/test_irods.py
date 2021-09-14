# -*- coding: utf-8 -*-
#
# Copyright © 2020, 2021 Genome Research Ltd. All rights reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# @author Keith James <kdj@sanger.ac.uk>

import hashlib
from datetime import datetime
from pathlib import PurePath
from unittest.mock import patch

import pytest
from pytest import mark as m

from partisan.exception import RodsError
from partisan.irods import AC, AVU, Baton, Collection, DataObject, Permission
from irods_fixture import (
    baton_session,
    ont_gridion,
    simple_collection,
    simple_data_object,
)

#  Stop IDEs "optimizing" away these imports

_ = baton_session
_ = simple_collection
_ = simple_data_object
_ = ont_gridion


@m.describe("AC")
class TestAC(object):
    @m.describe("Comparison")
    def test_compare_acs_equal(self):
        user = "irods"
        zone = "testZone"

        assert AC(user, Permission.OWN, zone=zone) == AC(
            user, Permission.OWN, zone=zone
        )

        assert AC(user, Permission.OWN, zone=zone) != AC(
            user, Permission.READ, zone=zone
        )

        assert AC(user, Permission.OWN, zone=zone) != AC(
            "public", Permission.OWN, zone=zone
        )

    def test_compare_acs_lt(self):
        user = "irods"
        zone = "testZone"

        assert AC(user, Permission.OWN, zone=zone) < AC(
            "public", Permission.OWN, zone=zone
        )

        assert AC(user, Permission.NULL, zone=zone) < AC(
            user, Permission.OWN, zone=zone
        )

    def test_compare_acs_sort(self):
        zone = "testZone"
        acl = [
            AC("zzz", Permission.OWN, zone=zone),
            AC("aaa", Permission.WRITE, zone=zone),
            AC("aaa", Permission.READ, zone=zone),
            AC("zyy", Permission.READ, zone=zone),
            AC("zyy", Permission.OWN, zone=zone),
        ]
        acl.sort()

        assert acl == [
            AC("aaa", Permission.READ, zone=zone),
            AC("aaa", Permission.WRITE, zone=zone),
            AC("zyy", Permission.OWN, zone=zone),
            AC("zyy", Permission.READ, zone=zone),
            AC("zzz", Permission.OWN, zone=zone),
        ]


@m.describe("AVU")
class TestAVU(object):
    @m.describe("Comparison")
    def test_compare_avus_equal(self):
        assert AVU("a", 1) == AVU("a", 1)
        assert AVU("a", 1, "mm") == AVU("a", 1, "mm")

        assert AVU("a", 1) != AVU("a", 1, "mm")

        assert AVU("a", 1).with_namespace("x") == AVU("a", 1).with_namespace("x")

        assert AVU("a", 1).with_namespace("x") != AVU("a", 1).with_namespace("y")

    def test_compare_avus_lt(self):
        assert AVU("a", 1) < AVU("b", 1)
        assert AVU("a", 1) < AVU("a", 2)

        assert AVU("a", 1, "mm") < AVU("a", 1)
        assert AVU("a", 1, "mm") < AVU("a", 2, "mm")
        assert AVU("a", 1, "cm") < AVU("a", 1, "mm")

        assert AVU("a", 1).with_namespace("x") < AVU("a", 1)
        assert AVU("z", 99).with_namespace("x") < AVU("a", 1)

        assert AVU("a", 1).with_namespace("x") < AVU("a", 1).with_namespace("y")

    def test_compare_avus_sort(self):
        x = [AVU("z", 1), AVU("y", 1), AVU("x", 1)]
        x.sort()
        assert x == [AVU("x", 1), AVU("y", 1), AVU("z", 1)]

        y = [AVU("x", 2), AVU("x", 3), AVU("x", 1)]
        y.sort()
        assert y == [AVU("x", 1), AVU("x", 2), AVU("x", 3)]

    def test_compare_avus_sort_ns(self):
        x = [AVU("z", 1).with_namespace("a"), AVU("y", 1), AVU("x", 1)]
        x.sort()

        assert x == [AVU("z", 1).with_namespace("a"), AVU("x", 1), AVU("y", 1)]

    def test_compare_avus_sort_units(self):
        x = [AVU("x", 1, "mm"), AVU("x", 1, "cm"), AVU("x", 1, "km")]
        x.sort()

        assert x == [AVU("x", 1, "cm"), AVU("x", 1, "km"), AVU("x", 1, "mm")]


@m.describe("Collection")
class TestCollection(object):
    @m.describe("Support for str path")
    @m.context("When a Collection is made from a str path")
    @m.it("Can be created")
    def test_make_collection_str(self, simple_collection, baton_session):
        p = PurePath(simple_collection)
        coll = Collection(baton_session, p.as_posix())

        assert coll.exists()
        assert coll.path == p

    @m.describe("Support for pathlib.Path")
    @m.context("When a Collection is made from a pathlib.Path")
    @m.it("Can be created")
    def test_make_collection_pathlib(self, simple_collection, baton_session):
        p = PurePath(simple_collection)
        coll = Collection(baton_session, p)

        assert coll.exists()
        assert coll.path == p

    @m.describe("Testing existence")
    @m.context("When a Collection exists")
    @m.it("Can be detected")
    def test_collection_exists(self, simple_collection, baton_session):
        p = PurePath(simple_collection)
        assert Collection(baton_session, p).exists()
        assert not Collection(baton_session, "/no/such/collection").exists()

    @m.it("Can be listed (non-recursively)")
    def test_list_collection(self, simple_collection, baton_session):
        coll = Collection(baton_session, simple_collection)
        assert coll.list() == Collection(baton_session, simple_collection)

        coll = Collection(baton_session, "/no/such/collection")
        with pytest.raises(RodsError, match="does not exist"):
            coll.list()

    @m.it("Can have its contents listed")
    def test_list_collection_contents(self, ont_gridion, baton_session):
        p = PurePath(
            ont_gridion,
            "66",
            "DN585561I_A1",
            "20190904_1514_GA20000_FAL01979_43578c8f",
        )

        coll = Collection(baton_session, p)
        contents = coll.contents()
        assert len(contents) == 11

    @m.it("Can have metadata added")
    def test_meta_add_collection(self, simple_collection, baton_session):
        coll = Collection(baton_session, simple_collection)
        assert coll.metadata() == []

        avu1 = AVU("abcde", "12345")
        avu2 = AVU("vwxyz", "567890")

        assert coll.meta_add(avu1, avu2) == 2
        assert avu1 in coll.metadata()
        assert avu2 in coll.metadata()

        assert (
            coll.meta_add(avu1, avu2) == 0
        ), "adding collection metadata is idempotent"

    @m.it("Can have metadata removed")
    def test_meta_rem_collection(self, simple_collection, baton_session):
        coll = Collection(baton_session, simple_collection)
        assert coll.metadata() == []

        avu1 = AVU("abcde", "12345")
        avu2 = AVU("vwxyz", "567890")
        coll.meta_add(avu1, avu2)

        assert coll.meta_remove(avu1, avu2) == 2
        assert avu1 not in coll.metadata()
        assert avu2 not in coll.metadata()
        assert (
            coll.meta_remove(avu1, avu2) == 0
        ), "removing collection metadata is idempotent"

    @m.it("Can be found by its metadata")
    def test_meta_query_collection(self, simple_collection, baton_session):
        coll = Collection(baton_session, simple_collection)

        avu = AVU("abcde", "12345")
        coll.meta_add(avu)
        assert coll.metadata() == [avu]

        found = baton_session.meta_query([avu], collection=True, zone=coll)
        assert found == [Collection(baton_session, simple_collection)]


@m.describe("DataObject")
class TestDataObject(object):
    @m.context("When a DataObject is made from a str path")
    @m.it("Can be created")
    def test_make_data_object_str(self, simple_data_object, baton_session):
        obj = DataObject(baton_session, simple_data_object.as_posix())

        assert obj.exists()
        assert obj.path == simple_data_object.parent
        assert obj.name == simple_data_object.name

    @m.context("When a DataObject is made from a pathlib.Path")
    @m.it("Can be created")
    def test_make_data_object_pathlib(self, simple_data_object, baton_session):
        obj = DataObject(baton_session, simple_data_object)

        assert obj.exists()
        assert obj.path == simple_data_object.parent
        assert obj.name == simple_data_object.name

    @m.describe("Operations on an existing DataObject")
    @m.context("When a DataObject exists")
    @m.it("Can be detected")
    def test_detect_data_object(self, simple_data_object, baton_session):
        assert DataObject(baton_session, simple_data_object).exists()
        assert not DataObject(baton_session, "/no/such/object.txt").exists()

    @m.it("Can be listed")
    def test_list_data_object(self, simple_data_object, baton_session):
        obj = DataObject(baton_session, simple_data_object)
        assert obj.list() == DataObject(baton_session, simple_data_object)

        obj = DataObject(baton_session, "/no/such/data_object.txt")
        with pytest.raises(RodsError, match="does not exist"):
            obj.list()

    @m.it("Can be got from iRODS to a file")
    def test_get_data_object(self, tmp_path, simple_data_object, baton_session):
        obj = DataObject(baton_session, simple_data_object)

        local_path = tmp_path / simple_data_object.name
        size = obj.get(local_path)
        assert size == 555

        md5 = hashlib.md5(open(local_path, "rb").read()).hexdigest()
        assert md5 == "39a4aa291ca849d601e4e5b8ed627a04"

    @m.it("Can be read from iRODS")
    def test_read_data_object(self, tmp_path, simple_data_object, baton_session):
        obj = DataObject(baton_session, simple_data_object)
        contents = obj.read()
        assert (
            hashlib.md5(contents.encode()).hexdigest()
            == "39a4aa291ca849d601e4e5b8ed627a04"
        )

    @m.it("Has a checksum")
    def test_get_checksum(self, simple_data_object, baton_session):
        obj = DataObject(baton_session, simple_data_object)
        assert obj.checksum() == "39a4aa291ca849d601e4e5b8ed627a04"

    @m.it("Can have its checksum verified as good")
    def test_verify_checksum_good(self, simple_data_object, baton_session):
        obj = DataObject(baton_session, simple_data_object)

        # Note that in iRODS >= 4.2.10, this always passes, even if the remote file
        # is the wrong size of has a mismatching checksum, because of this iRODS bug:
        # https://github.com/irods/irods/issues/5843
        assert obj.checksum(verify_checksum=True)

    @m.it("Can have its checksum verified as bad")
    def test_verify_checksum_bad(self, simple_data_object, baton_session):
        obj = DataObject(baton_session, simple_data_object)

        # We are patching json.loads object hook for decoding baton.py JSON
        decoded = {
            Baton.OP: Baton.CHECKSUM,
            Baton.ARGS: {"verify": True},
            Baton.TARGET: {
                Baton.COLL: simple_data_object.parent,
                Baton.OBJ: simple_data_object.name,
            },
            Baton.RESULT: {Baton.SINGLE: None},
            Baton.ERR: {Baton.MSG: "Checksum validation failed", Baton.CODE: -999},
        }

        with patch("partisan.irods.as_baton") as json_mock:
            json_mock.return_value = decoded
            with pytest.raises(RodsError) as info:
                obj.checksum(verify_checksum=True)
                assert info.value.code == decoded[Baton.ERR][Baton.CODE]

    @m.it("Can be overwritten")
    def test_overwrite_data_object(self, tmp_path, simple_data_object, baton_session):
        obj = DataObject(baton_session, simple_data_object)

        local_path = tmp_path / simple_data_object.name
        with open(local_path, "w") as f:
            f.write("test\n")

        obj.put(local_path, calculate_checksum=False, verify_checksum=True)
        assert obj.exists()
        assert obj.checksum() == "d8e8fca2dc0f896fd7cb4cb0031ba249"

    @m.it("Can add have metadata added")
    def test_meta_add_data_object(self, simple_data_object, baton_session):
        obj = DataObject(baton_session, simple_data_object)
        assert obj.metadata() == []

        avu1 = AVU("abcde", "12345")
        avu2 = AVU("vwxyz", "567890")

        obj.meta_add(avu1, avu2)
        assert avu1 in obj.metadata()
        assert avu2 in obj.metadata()

        assert (
            obj.meta_add(avu1, avu2) == 0
        ), "adding data object metadata is idempotent"

    @m.it("Can have metadata removed")
    def test_meta_rem_data_object(self, simple_data_object, baton_session):
        obj = DataObject(baton_session, simple_data_object)
        assert obj.metadata() == []

        avu1 = AVU("abcde", "12345")
        avu2 = AVU("vwxyz", "567890")
        obj.meta_add(avu1, avu2)

        assert obj.meta_remove(avu1, avu2) == 2
        assert avu1 not in obj.metadata()
        assert avu2 not in obj.metadata()
        assert (
            obj.meta_remove(avu1, avu2) == 0
        ), "removing data object metadata is idempotent"

    @m.it("Can have metadata replaced")
    def test_meta_rep_data_object(self, simple_data_object, baton_session):
        obj = DataObject(baton_session, simple_data_object)
        assert obj.metadata() == []

        avu1 = AVU("abcde", "12345")
        avu2 = AVU("vwxyz", "567890")
        obj.meta_add(avu1, avu2)

        assert obj.meta_supersede(avu1, avu2) == (
            0,
            0,
        ), "nothing is replaced when new all AVUs == all old AVUs"
        assert obj.metadata() == [avu1, avu2]

        assert obj.meta_supersede(avu1) == (
            0,
            0,
        ), "nothing is replaced when one new AVU is in the AVUs"
        assert obj.metadata() == [avu1, avu2]

        avu3 = AVU("abcde", "88888")
        obj.meta_add(avu3)

        # Replace avu1, avu3 with avu4, avu5 (leaving avu2 in place)
        avu4 = AVU("abcde", "99999")
        avu5 = AVU("abcde", "00000")
        date = datetime.utcnow()
        assert obj.meta_supersede(avu4, avu5, history=True, history_date=date) == (
            2,
            3,
        ), "AVUs sharing an attribute with a new AVU are replaced"

        date = date.isoformat(timespec="seconds")
        history = AVU("abcde_history", f"[{date}] {avu1.value},{avu3.value}")
        expected = [avu2, avu4, avu5, history]
        expected.sort()
        assert obj.metadata() == expected

    @m.it("Can be found by its metadata")
    def test_meta_query_data_object(self, simple_data_object, baton_session):
        obj = DataObject(baton_session, simple_data_object)

        avu = AVU("abcde", "12345")
        obj.meta_add(avu)
        assert obj.metadata() == [avu]

        found = baton_session.meta_query([avu], data_object=True, zone=obj.path)
        assert found == [DataObject(baton_session, simple_data_object)]

    @m.it("Can have access controls added")
    def test_add_ac_data_object(self, simple_data_object, baton_session):
        zone = "testZone"
        user = "irods"
        obj = DataObject(baton_session, simple_data_object)
        assert obj.acl() == [AC(user, Permission.OWN, zone=zone)]

        assert (
            obj.ac_add(AC(user, Permission.OWN, zone=zone)) == 0
        ), "nothing is replaced when new ACL == all old ACL"
        assert obj.acl() == [AC(user, Permission.OWN, zone=zone)]

        assert obj.ac_add(AC("public", Permission.READ, zone=zone)) == 1
        assert obj.acl() == [
            AC(user, Permission.OWN, zone=zone),
            AC("public", Permission.READ, zone=zone),
        ]

    @m.it("Can have access controls removed")
    def test_rem_ac_data_object(self, simple_data_object, baton_session):
        zone = "testZone"
        user = "irods"
        obj = DataObject(baton_session, simple_data_object)
        assert obj.acl() == [AC(user, Permission.OWN, zone=zone)]

        assert (
            obj.ac_rem(AC("public", Permission.READ, zone=zone)) == 0
        ), "nothing is removed when the access control does not exist"
        assert obj.acl() == [AC(user, Permission.OWN, zone=zone)]

        assert obj.ac_add(AC("public", Permission.READ, zone=zone)) == 1
        assert obj.acl() == [
            AC(user, Permission.OWN, zone=zone),
            AC("public", Permission.READ, zone=zone),
        ]

        assert obj.ac_rem(AC("public", Permission.READ, zone=zone)) == 1
        assert obj.acl() == [AC(user, Permission.OWN, zone=zone)]
