#!/usr/bin/python
# -*- coding: utf-8 -*-

from google.protobuf.descriptor_pb2 import FileDescriptorSet
from proto_meta import *


"""
message FileDescriptorProto {
    optional string name = 1;              // proto文件名，file name，相对于源代码根目录 
    optional string package = 2;           // proto包名，例如 "foo"、"foo.bar"
    repeated string dependency = 3;        // proto文件中import进来的其他proto文件列表
    repeated int32 public_dependency = 10; // 上面public import的proto文件在proto文件列表中的索引

    // Indexes of the weak imported files in the dependency list.
    repeated int32 weak_dependency = 11;   // 上面weak import的proto文件在proto文件列表中的索引，不要使用，只用于google内部的迁移

    // proto文件中的所有顶层定义信息
    repeated DescriptorProto message_type = 4;    // 所有的消息(message)类型定义
    repeated EnumDescriptorProto enum_type = 5;   // 所有的枚举(enum)类型定义
    repeated ServiceDescriptorProto service = 6;  // 所有的服务(service)类型定义
    repeated FieldDescriptorProto extension = 7;  // 所有的扩展字段定义

    optional FileOptions options = 8;             // 文件选项

    // 这个字段包括了源代码的相关信息，这里的信息可以给开发工具使用，也仅应该提供给开发工具使用；
    // 可以选择将这个字段中的信息删除，在程序运行期间并不会造成破坏。
    optional SourceCodeInfo source_code_info = 9;
}
"""


class ProtoParser(object):
    """"解析protoc生成的proto文件描述信息，将其转换成ProtoMeta信息"""

    def __init__(self):
        self._reference_message_name = set()
        # self._custom_labels = None
    def parse(self, descfilename, allmeta):
        """解析传入的desc文件，转换成ProtoMeta信息
        Args:
            desc_file_path: protoc --descriptor_set_out --include_source_info
                编译生成的proto描述文件
        Returns:
            A dict mapping message name and ProtoMeta
        """
        with open(descfilename, "rb") as f:
            desc = FileDescriptorSet.FromString(f.read())
            for onefile in desc.file:
                allmeta.add(self.parse_file(onefile))

        # for proto_message_meta in proto_meta_mgr.metas:
        #     if proto_message_meta.name in self._reference_message_name:
        #         proto_message_meta.is_reference_message = True

        return allmeta

    def parse_file(self, onefile):
        print("parse one proto file, "+onefile.name)
        metas = []
        for idx in range(len(onefile.message_type)):
            onemsg = onefile.message_type[idx]
            #print("parse one msg, "+ onemsg.name)
            msgdesc = self.parse_message(onemsg, onefile.source_code_info, idx)
            metas.append(msgdesc)
        return metas

    def parse_message(self, msgdesc, source_code_info, msgidx):
        # 解析message本身
        # 4指message_type
        #custom_labels = self.parse_message_comments(msgidx, source_code_info, 4)
        msgmeta = ProtoMessageMeta(msgdesc.name, msgdesc)
        # 解析消息中的字段
        for fieldidx, fielddesc in enumerate(msgdesc.field):
            commentlabel = self.parse_field_comments(source_code_info, msgidx, fieldidx, 4)
            fieldmeta = ProtoMessageFieldMeta(
                fielddesc.name,
                commentlabel,
                fielddesc.number,
                fielddesc.type,
                self.parse_field_type_name(fielddesc.type_name),
                fielddesc.label,
                fielddesc
            )
#            print(fieldmeta.__dict__)
            msgmeta.fields.append(fieldmeta)
        return msgmeta

    # def parse_message_comments(self, message_index, source_code_info, descriptor_field_number):
    #     location_filter = lambda location: len(location.path) == 2 and \
    #                                        location.path[0] == descriptor_field_number and \
    #                                        location.path[1] == message_index
    #     comments = self.find_comments(location_filter, source_code_info)
    #     return self.parse_comments(comments)

    def find_comments(self, location_filter, source_code_info):
        for one in source_code_info.location:
            if one.trailing_comments and location_filter(one):
                return one.trailing_comments
        return None

    #[needsync:1, max_count:2]
    def getStringInter(self, line, head, tail, inter):
        labels = {}

        if not line:
            return labels

        p1 = line.find(head)
        p2 = line.find(tail, p1 + len(head))
        if p1<0 or p2<=0:
            return labels

        ret = line[p1 + len(head):p2]
        ret = ret.strip()
        arr = ret.split(",")
        for one in arr:
            kv = one.split(":")
            labels[kv[0]] = kv[1]
        return labels

    #hx2proto.fieldname, del namespace
    def parse_field_type_name(self, type_name):
        if type_name:
            if type_name.startswith("."):
                return type_name[type_name.rfind(".") + 1:].strip()
            else:
                return type_name.strip()
        return None

    def parse_field_comments(self, source_code_info, msgidx, fieldidx, basetype_filed_num):
        # field_index并不是message中field定义中的number，而是field在message中声明的顺序，第一个是0，依次往后增加，中间不会有跳过的情况
        #msgfield:[4, msgidx, 2, fieldidx]
        location_filter = lambda location: len(location.path) == 4 and \
                                           location.path[0] == basetype_filed_num \
                                           and location.path[2] == 2 and \
                                           location.path[1] == msgidx \
                                           and location.path[3] == fieldidx 
        comments = self.find_comments(location_filter, source_code_info)
        return self.getStringInter(comments, "[", "]", ":")

    # def parse_enum(self, enum_descriptor_proto, source_code_info, enum_index):
    #     # 5指enum_type
    #     custom_labels = self.parse_message_comments(enum_index, source_code_info, 5)
    #     proto_enum_meta = ProtoEnumMeta(enum_descriptor_proto.name, custom_labels)
    #     fields = self.parse_enum_fields(enum_descriptor_proto, source_code_info, enum_index)
    #     proto_enum_meta.fields = fields
    #     return proto_enum_meta
    #
    # def parse_enum_fields(self, enum_descriptor_proto, source_code_info, enum_index):
    #     return [self.parse_enum_field(source_code_info, enum_index, field_index, enum_value_descriptor_proto)
    #             for field_index, enum_value_descriptor_proto in enumerate(enum_descriptor_proto.value)]
    #
    # def parse_enum_field(self, source_code_info, enum_index, field_index, enum_value_descriptor_proto):
    #     custom_labels = self.parse_field_comments(source_code_info, enum_index, field_index, 5)
    #     proto_enum_field_meta = ProtoEnumFieldMeta(
    #         enum_value_descriptor_proto.name,
    #         custom_labels,
    #         enum_value_descriptor_proto.number)
    #     return proto_enum_field_meta
