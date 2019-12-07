# 基于pb的real-ghost数据自动同步机制



## 背景

出于解耦、提高扩展性、提高承载等目的，很多业务将会分散在不同的进程。

为了防止数据冲突和保证一致性，一般会将某数据的计算统一到一个进程内，而在其他进程内部出于模块交互的需要，也要存在一份拷贝。

在原计算进程中的对象我们称为主对象，即：realobj。

在其他进程中的拷贝我们称为镜像对象，即：ghostobj。

当realobj发生数据变化时，某些数据需要同步给ghostobj，每次数据修改的时候都要手写同步消息。



## 愿景

1. 数据修改后自动同步：通过在协议文件中，把某些字段标记为需要同步，在调用数据修改接口后，框架能自动将修改的数据同步给所有ghost。
2. 数据同步的时机：对字段的修改能支持立即同步（业务需要），后续tick同步（合包减少包量）

总之，要有一套通用的，自动的，数据同步机制，来简化后续的日常迭代开发工作。每次新增全新real对象或者已有real中新增同步字段时，不用手写同步消息。



## 应用场景

如无缝大世界中单位（玩家或者怪物）在边界时，单位在对岸服务器可能需要一个ghost，用于消息转发或战斗计算。

如氏族（帮派）、家族、婚姻、结义、队伍、聊天群组等社交关系，计算进程应该在某个关系服务器，而其他的场景服务器需要读取这些数据，所以也要有ghost。



## 实现设计

采用keyvalue的方式同步，脚本生成相关配置和代码，自动生成数据修改的接口供业务层调用。

### 难点：

- key的统一：需要支持嵌套字段的定位，
- value的统一：收集同步列表，使用oneof为一个同步unit

收集同步列表，每个同步字段成为message的oneof里的一种，使用oneof的tag作为key， oneof的内容作为value。

### 具体方案：

#### 1. 通用定义

```protobuf
//realghost属性自动同步框架
//操作类型
enum AutoSyncOpType
{
    AutoSyncOpType_SingleReplace    = 0;    //单个元素替换
    AutoSyncOpType_ListReplace      = 1;    //列表元素替换
    AutoSyncOpType_ListAdd          = 2;    //列表元素添加
    AutoSyncOpType_ListDel          = 3;    //列表元素删除
};

//单次修改列表，将添加到Test中
message AutoSyncChangeUnit
{
    int32 ChangeDataKey     = 1; //对应SSTestAutoSyncUnit中oneof的fieldNum，用于定位修改字段
    int32 OpType            = 2; //操作类型，AutoSyncOpType
    repeated int64 OpParam  = 3; //[max_count:2]，如果optype是对数组操作，这里需要记录unit在数组中的key，方便后续发起同步时定位到list中的unit
};
```



#### 2. 【用户操作】标记同步字段与添加同步列表

用户在Test的pb定义文件中，标记需要同步的字段，注释里加上[RealGhostSync:Test]，

如Test对象配置如下：

```protobuf

//---------------Test.proto------------------
message SubMsg
{
	int32 sub = 1; //[RealGhostSync:Test]
};

message ConndInfo
{
	int32 id = 1;
	SubMsg data = 2;
};


message TriggerDAta
{
	int32 id = 1;
	SubMsg data = 2;
};

//unit
message Test
{
    uint64 ID           = 1; // 对象ID
    int32 Type          = 2; // 类型[RealGhostSync:Test]
    int32 CreateTime    = 3;
    int32 Status        = 5; //[RealGhostSync:Test]
	oneof TypeData
	{
		int32 Statu = 10;	//[RealGhostSync:Test]
		TriggerDAta triger 	= 11;//[RealGhostSync:Test]
		ConndInfo Conn = 12;
	}
	oneof TypeData2
	{
		int32 BBB = 20;	//[RealGhostSync:Test]
	}
	oneof TypeData3
	{
		int32 ccc = 30;	//[RealGhostSync:Test]
	}
};

//-----------------------------------------------------------
//-------init add tmmplate to auto sync proto:star_real_ghost_autosync.proto-----------
//将Test确认为需要同步的基础对象之一时，下列模板添加一次即可
//unit
message TestAutoSyncUnit
{
	int32 OpType = 1; 	//操作类型，参见AutoSyncOpType，单个或者列表操作
	oneof TypeData
	{	
		int32 Reserve = 10;
		//(DONOT DELETE THIS LINE!!! AutoSyncAddHere for Test)
		//... 后续新增同步字段，将自动追加到这里
	}
};

//ssmsg
message SSMsgTestAutoSyncList
{
	repeated TestAutoSyncUnit List = 1;
};

//todo添加 SSMsgTestAutoSyncList 到ssmsg中
```

为了兼容某嵌套字段，在其他父message中设置为不同步的情况，所以在标记字段需要同步时，也显式的标明属于哪个同步对象

> 这里有个疑义：
>
> 标记嵌套消息的子结构体的成员需要同步，为了方便起见，直接在最后的成员上标记，而不用标记所有父类。
>
> 这样有个问题，就是这个结构体如果在Test的其他成员中也用到，即Test的语法树的不同分支下有2个相同的该结构体被实例化，则会用同样的同步规则配置。
>
> 如果要明确标记区分具体某个分支下才同步，则将给标记工作带来较大的复杂度，而这个情况并不是很多，处理起来性价比也不高，所以目前暂时不处理这个情况。

#### 3. 【框架生成】生成差异化自动同步协议

根据1中的用户在pb协议里的配置，将自动生成自动同步的unit的oneof。处理步骤如下：

- 解析pb文件中Test的定义，将有标记[RealGhostSync:Test]字段（包括嵌套消息），按照顺序全部收集起来作为newsynclist。
  
> 【**字段名的生成**】
> 记录field的所有递归层级上的parent_field，这些parent_field和自己的name（需要注意oneof成员）组合为最后同步unit字段的name，这样的name的好处是：
>
> - 生成的后续生成oneof的key作为setvalue接口时有layer信息，可读性更强
>
> - 完全避免字段的冲突
>
>   另外，生成对应的layernum用于与原有proto比较是否存在。
>

> 【 **oneof的成员名生成**】
> 字段后续在生成的setvalue/getvalue接口中需要用到这个变量，而如果变量是oneof内的成员时，访问该变量时oneof本身的name必须包含在内，但是field本身的name并不包括oneof的name，所以如果直接使用field的name则无法访问到变量。
>
> 如：
>
> ```
> message Test
> {
> 	oneof TypeData
> 	{
> 		RoleInfo Role = 1;		//需要关注的field
> 		MonsterInfo Monster = 2;
> 	}
> }
> ```
>
> 
>
> 其中Role是TypeData的oneof的一员，则field里的name只有role，将需要额外解析field隶属的父msg（Test）的第几个oneof（index），用这个index到msg中的oneof_decl中读取到对应oneof的name，并组合在一起才是最后的能访问的变量名：stTypeData.stRole
>



- 读取原有的自动同步协议中的同步字段作为oldsynclist
- 将newsynclist-oldsynclist，差集diffsynclist作为此次新增的同步字段

> 【此处必须做差集】
>
> 否则将出现新增字段如果在原有同步字段列表中间时，如果直接用新的同步列表覆盖，某些field则将与旧的同步列表中的fieldnum不一致，相当于修改了pb的fieldnum对应的数据结构，导致最后同步时解包错位，这个违背pb本身的规则的，即定了字段后字段的tag序号不能修改。

- 读取star_real_ghost_autosync.proto，跟flag定位到需要写入的位置，将diffsynclist中的字段插入 star_real_ghost_autosync.proto中。



到此，同步协议自动生成完毕。

oneof中的field序号即后续pb自动生成的enum，即作为setvalue接口的key，从而统一了key并支持嵌套。

如对应Test的如上配置，将自动修改同步协议的文件：star_real_ghost_autosync.proto，追加新增的同步unit：

```protobuf
//unit
message TestAutoSyncUnit
{
	int32 OpType = 1;							//操作类型，参见AutoSyncOpType，单个或者列表操作
	oneof TypeData
	{	
		int32 Reserve = 10;
		int32 Type = 11; // [origfieldnumlayer:2, addtime:2019-12-07_23-04-59]
		int32 TypeData_Statu = 12; // [origfieldnumlayer:10, addtime:2019-12-07_23-04-59]
		TriggerDAta TypeData_triger = 13; // [origfieldnumlayer:11, addtime:2019-12-07_23-07-41]
		int32 TypeData_Conn_data_sub = 14; // [origfieldnumlayer:12_2_1, addtime:2019-12-07_23-07-41]
		int32 TypeData2_BBB = 15; // [origfieldnumlayer:20, addtime:2019-12-07_23-07-41]
		int32 TypeData3_ccc = 16; // [origfieldnumlayer:30, addtime:2019-12-07_23-07-41]
		int32 akter = 17; // [origfieldnumlayer:60, addtime:2019-12-07_23-07-41]
		//(DONOT DELETE THIS LINE!!! AutoSyncAddHere for Test)
		//... 后续新增同步字段，将自动追加到这里
	}
};
```



#### 4. 【框架生成】real的数据修改接口

在Test内部自动生成setvalue的实现， 供应用层调用，接口大致为：

```c++
struct Test
{
    uint64_t ullID;
    ...//other member
        
    template<typename T>
    int set_autosync_value(int key, const T& in, bool bIsImmiSync)
    {
    	switch(key)    
        {
            case ChangeVarNameField:
                iStatus = in;
                break;
            ...
            default:break;
        }
        
        add_change_to_sync_list(key);	// 内部判重
        if(bIsImmiSync)
        {
            sync_all_change_to_ghost();
        }
	};
```

自动生成setvalue接口内部的实现，函数实现包括：

- 根据key定位修改字段，并修改数据。

- 修改后的key加入修改列表（判重）
- 处理是否立即同步

#### 5. 【框架生成】real的tick发起数据同步接口

接口为：

```c++
int tick_sync_autosync_change_list();
```

接口内部将检查之前未同步的修改列表，并给所有的ghost发送同步消息。

此处要求：Test自身支持给所有ghost广播消息的接口：

```c++
int broadcast_real_msg_to_all_ghost(const SSMsg& msg);
```

#### 6. 【框架生成】ghost的接受数据同步口

Test将提供接受real同步过来的刷新数据的接口：

```c++
int fresh_data_as_ghost(const SSTestAutoSyncUnit& freshlist);
```

其内部将根据对于每个unit，修改相关的数据。从而实现数据同步。