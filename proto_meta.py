#!/usr/bin/python
# -*- coding: utf-8 -*-

from google.protobuf.descriptor_pb2 import FieldDescriptorProto
from google.protobuf.descriptor import *
import sys

class ProtoMeta:
    """proto meta基类"""
    def __init__(self, name, custom_labels):
        """ 初始化

        Args:
            name: proto中定义的英文名字
            custom_labels: 字段用//@添加的所有标签
        """
        self.name = name
        self.custom_labels = custom_labels

    def contain_custom_label(self, custom_label):
        """ 是否包含自定义标签

        Args:
            custom_label: 查询的标签

        Returns:
            True 包含，False 不包含
        """
        return custom_label in self.custom_labels \
            if self.custom_labels is not None and custom_label is not None else True

    def get_custom_label_value(self, custom_label):
        return self.custom_labels.get(custom_label)


class ProtoFieldBaseMeta(ProtoMeta):
    """proto field meta基类，子类ProtoMessageFieldMeta和ProtoEnumFieldMeta"""
    def __init__(self,
                 name,
                 custom_labels,
                 field_number):
        """ 初始化

        Args:
            name: 字段英文名字
            field_number: 字段的序号
        """
        ProtoMeta.__init__(self, name, custom_labels)
        self.field_number = field_number


class redirect:
    content = ""
    def write(self, str):
        self.content += str

class ProtoMessageFieldMeta(ProtoFieldBaseMeta):
    """proto message field 字段描述信息 """
    def __init__(self,
                 name,
                 custom_labels,
                 field_number,
                 field_type,
                 field_type_name,
                 field_label_type,
                 fieldproto):
        """ 初始化

        Args:
            name: 字段英文名字
            custom_labels: 字段用//@添加的所有标签
            field_type: 字段值类型，对应FieldDescriptorProto.Type枚举
            field_type_name: string类型，字段值类型名字，字段是Message或者Enum时，设置这个字段的值为对应的类型名字，
                如果是protobuf内置类型，只需要设置field_type，不需要设置field_type_name
            field_number: 字段的序号
            field_label_type: 字段的label，对应FieldDescriptorProto.Label枚举
        """
        ProtoFieldBaseMeta.__init__(self, name, custom_labels, field_number)
        self.field_type = field_type
        self.field_type_name = field_type_name
        self.field_label_type = field_label_type
        self.fieldproto = fieldproto

    def get_field_type_name_without_T(self):
        return self.field_type_name[1:]

    def get_layer_num_list(self):
        ret = ""
        idx = 0
        for field in self.parent_field:
            ret += str(field.field_number)
            ret += "_"
        ret += str(self.field_number)
        return ret

    def getvarname(self):
        if hasattr(self, "parent_oneof_name"):
            return self.parent_oneof_name+"_"+self.name
        else:
            return self.name

    def get_layer_var_list(self):
        ret = ""
        idx = 0
        for field in self.parent_field:
            ret += (field.getvarname())
            ret += "_"
        ret += self.getvarname()
        return ret

    '''
    name: "Statu"
    number: 10
    label: LABEL_OPTIONAL
    type: TYPE_INT32
    oneof_index: 0
    json_name: "Statu"
    '''
    def get_oneof_index(self):
        origout = sys.stdout
        r = redirect()
        sys.stdout = r
        print(self.fieldproto)
        sys.stdout = origout
        arr = r.content.split("\n")
        for one in arr:
            kv = one.split(":")
            if kv[0].strip() == "oneof_index":
                return int(kv[1].strip())
        return -1




class ProtoEnumFieldMeta(ProtoFieldBaseMeta):
    """proto enum field 类型描述信息 """
    def __init__(self,
                 name,
                 custom_labels,
                 field_number):
        """ 初始化

        Args:
            name: 字段英文名字
            custom_labels: 字段用//@添加的所有标签
            field_number: 字段的序号
        """
        ProtoFieldBaseMeta.__init__(self, name, custom_labels, field_number)


class ProtoMessageBaseMeta(ProtoMeta):
    """proto message 基类"""
    def __init__(self, name):
        """ 初始化
            Message和Enum不需要tag标签，只有Message Field才需要tag标签

        Args:
            name: 英文名字
            custom_labels: 字段用//@添加的所有标签
        """
        ProtoMeta.__init__(self, name, None)

    def get_name_without_T(self):
        return self.name[1:]

    def get_lower_name_without_T(self):
        return self.get_name_without_T().lower()


class ProtoMessageMeta(ProtoMessageBaseMeta):
    """proto message 描述信息"""
    def __init__(self, name, srcdesc):
        """ 初始化

        Args:
            name: message英文名字
            custom_labels: 字段用//@添加的所有标签
        """
        ProtoMessageBaseMeta.__init__(self, name)
        self.fields = []  # 字段列表，列表中字段顺序和proto中字段定义顺序相同
        self.srcdesc = srcdesc

    def add_field(self, proto_message_field_meta):
        self.fields.append(proto_message_field_meta)

    def get_fields_with_tag(self, tag):
        return [field for field in self.fields if field.should_keep_field(tag)]



class ProtoMetaMgr():
    def __init__(self):
        self._metas = []  # value: ProtoMessageBaseMeta

    @property
    def metas(self):
        return self._metas

    def add(self, proto_message_base_meta):
        self.metas.extend(proto_message_base_meta)

    def get_proto_message_base_meta(self, name):
        return next(proto_message_base_meta
                    for proto_message_base_meta in self._metas if proto_message_base_meta.name == name)
