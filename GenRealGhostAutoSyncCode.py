#!/usr/bin/python
# -*- coding: UTF-8 -*-
# @brief 为了支持real属性变化时，自动同步到ghost，本脚本将根据协议配置自动生成以下内容
# 1. 自动同步的协议
# 2. real对象的修改数据接口
# 3. real对象的tick发起同步接口
# 4. ghost对象数据接收刷新接口
# @author alexxfxiao
# @date 2019-12-05


import os
import sys
import copy
import time
import io

from proto_parser import ProtoParser
from proto_meta import ProtoMessageMeta
from proto_meta import ProtoMetaMgr

class CfgEntity:
    def __init__(self, name__):
        self.name = name__

#####################config begin######################
g_cfgFileDescriptorFile="t.desc"
g_cfgEntityList = [
    CfgEntity("Test"),
        ]

g_cfgFieldLayerLabel = 'origfieldnumlayer'
g_cfgInsertPosHead = 'DONOT DELETE THIS LINE!!! AutoSyncAddHere for '
g_cfgAutoSyncProtoFile = 'star_real_ghost_autosync.proto'
#######################################################

g_allmeta = ProtoMetaMgr()
def find_msg_meta(name):
    for msg in g_allmeta.metas:
        if msg.name == name:
            return msg
    return None

#扫描pb协议
g_parent_field_list = []
def initenv():
    global g_parent_field_list
    g_parent_field_list = []


def gen_sync_list_in_msg_by_flag(msgname, basemsgname, synclist):
    global  g_parent_field_list
    msg = find_msg_meta(msgname)

    for field in msg.fields:
        #{'name': 'TriggerList', 'custom_labels': {}, 'field_number': 15, 'field_type': 11, 'field_type_name': 'TriggerList', 'field_label_type': 1}
        #{'name': 'Status', 'custom_labels': {'RealGhostSync': 'Object'}, 'field_number': 5, 'field_type': 5, 'field_type_name': None, 'field_label_type': 1}
        #print(field.__dict__)

        #parent oneof_index
        oneof_index = field.get_oneof_index()
        if oneof_index >= 0:
            field.parent_oneof_name = msg.srcdesc.oneof_decl[oneof_index].name

        if "RealGhostSync" in field.custom_labels and field.custom_labels['RealGhostSync'] == basemsgname:
            field.parent_field = copy.deepcopy(g_parent_field_list)
            synclist.append(field)
        elif field.field_type == 11:
            g_parent_field_list.append(field)
            gen_sync_list_in_msg_by_flag(field.field_type_name, basemsgname, synclist)
            g_parent_field_list.pop()


def read_old_sync_list(name, synclist):
    syncUnitName = name + "AutoSyncUnit"
    msg = find_msg_meta(syncUnitName)
    if not msg:
        print("no auto unit message define, name:"+syncUnitName)
        exit(1)
    for field in msg.fields:
        #保留字段
        if field.field_number < 10:
            continue
        synclist.append(field)

g_typestr = {
    1: "double" ,
    2 : "float" 	,
    3 : "int64" 	,
    4 : "uint64" 	,
    5 : "int32" 	,
    6 : "fixed64" 	,
    7 : "fixed32" 	,
    8 : "bool" 		,
    9 : "string" 	,
    10: "group" 	,
    11: "message" 	,
    12: "bytes" 	,
    13: "uint32" 	,
    14: "enum" 		,
    15: "sfixed32" 	,
    16: "sfixed64" 	,
    17: "sint32" 	,
    18: "sint64" 	,

}

def gettime():
    return time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
g_cfgcurtime = gettime()

#{'name': 'Status', 'custom_labels': {'RealGhostSync': 'Object'}, 'field_number': 5, 'field_type': 5, 'field_type_name': None, 'field_label_type': 1, 'layer_idx': '5', 'layer_name': 'Status'}
#{'name': 'ConnInfo', 'custom_labels': {'RealGhostSync': 'Object'}, 'field_number': 1, 'field_type': 11, 'field_type_name': 'ConndInfo', 'field_label_type': 1, 'layer_idx': '60_1', 'layer_name': 'Role_ConnInfo'}
#-->ConndInfo TypeData_Data_Connd 	= 11;//[origfieldnumlayer:60_1]
def gen_field_declare_line(field, idx):
    typestr = g_typestr[field.field_type]
    if not typestr:
        raise "field type wrong:"+field.field_type
    if typestr=="message":
        typestr = field.field_type_name
    return typestr + " " + field.get_layer_var_list() + " = " + str(idx) +\
            "; // ["+g_cfgFieldLayerLabel+":" + field.get_layer_num_list() + ", addtime:" + g_cfgcurtime +"]"


def out_put_diff_to_proto(name, diff, oldcount):
    if len(diff)==0:
        print("no new auto sync unit add, is same with old config!!! finish")
        return

    print("--begin out new line--")
    oldfile = io.open(g_cfgAutoSyncProtoFile, "r", encoding="utf-8")
    newfile = io.open(g_cfgAutoSyncProtoFile+".new", "w", encoding="utf-8")
    for line in oldfile:
        if line.find(g_cfgInsertPosHead+name)>=0:
            for newidx in range(len(diff)):
                outline = gen_field_declare_line(diff[newidx], newidx+oldcount+10)      #10个预留为前面的base字段
                print("add new line:"+outline)
                newfile.write("		" + outline + "\n")
        newfile.write(line)
    oldfile.close()
    newfile.close()
    os.system("copy " + g_cfgAutoSyncProtoFile + ".new " + g_cfgAutoSyncProtoFile)

def gen_auto_one(entity):
    initenv()

    #find and gen new sync gen
    new_synclist = []
    gen_sync_list_in_msg_by_flag(entity.name, entity.name, new_synclist)
    print("--new sync list--")
    [print(e.fieldproto) for e in new_synclist]
    # for e in new_synclist:
    #     oneof_idx = e.get_oneof_index()
    #     print("oneof_index:"+ str(oneof_idx))

    #read old sync list
    old_synclist = []
    read_old_sync_list(entity.name, old_synclist)
    print("--old sync list--")
    [print(e.__dict__) for e in old_synclist]

    #compare diff=new-old
    diff = []
    for newone in new_synclist:
        isExist = False
        for oldone in old_synclist:
            oldonelayer = ""
            if g_cfgFieldLayerLabel in oldone.custom_labels:
                oldonelayer = oldone.custom_labels[g_cfgFieldLayerLabel]
            if newone.get_layer_num_list() == oldonelayer:
                isExist = True
                break
        if not isExist:
            diff.append(newone)

    #output diff to auto.proto
    out_put_diff_to_proto(entity.name, diff, len(old_synclist))


def autogen():
    #gen desc
    os.system("protoc.exe -o "+g_cfgFileDescriptorFile+" star_real_ghost_autosync.proto t.proto  --include_source_info")

    #parse
    global  g_allmeta
    ProtoParser().parse(g_cfgFileDescriptorFile, g_allmeta)

    #do object/clan
    for i in range(len(g_cfgEntityList)):
        entity = g_cfgEntityList[i]
        print("----- gen entity:"+entity.name+" begin-----")
        if not gen_auto_one(entity):
            return
    
        print("----- gen entity:"+entity.name+" end  -----")
    

if __name__ == "__main__":
    autogen()
