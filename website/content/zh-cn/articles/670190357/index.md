---
title: '为什么说 C/C++ 编译器不保留元信息？'
date: 2023-12-03 23:37:51
updated: 2024-11-30 18:08:55
series: ['Reflection']
series_order: 2
---

## 首先什么是元信息？ 

来看下面一段`python`代码，我们希望能够根据传入的字符串来自动修改对应的字段值

```python
class Person:
    def __init__(self, age, name):
        self.age = age
        self.name = name

person = Person(10, "xiaohong")
setattr(person, "age", 12)
setattr(person, "name", "xiaoming")
print(f"name: {person.name}, age: {person.age}") # => name: xiaoming, age: 12
```

`setattr`是`python`内置的一个函数，刚好可以实现我们的需求。根据输入的字段名，修改对应值。

如果想要在`C++`中实现应该怎么办呢？`C++`可没有内置`setattr`这种函数。代码示例如下。（暂时就先考虑可以直接`memcpy`的类型了，也就是`trivially copyable`的类型）

```cpp
struct Person
{
    int age;
    std::string_view name;
};

// 名字 -> 字段偏移量，字段大小
std::map<std::string_view, std::pair<std::size_t, std::size_t>> fieldInfo = 
{
    {"age",  {offsetof(Person, age),  sizeof(int)}},
    {"name", {offsetof(Person, name), sizeof(std::string_view)}},
};

void setattr(Person* point, std::string_view name, void* data)
{
    if (!fieldInfo.contains(name))
    {
        throw std::runtime_error("Field not found");
    }
    auto& [offset, size] = fieldInfo[name];
    std::memcpy(reinterpret_cast<char*>(point) + offset, data, size);
}

int main()
{
    Person person = {.age = 1, .name = "xiaoming"};
    int age = 10;
    std::string_view name = "xiaohong";
    setattr(&person, "age", &age);
    setattr(&person, "name", &name);
    std::cout << person.age << " " << person.name << std::endl;
    // => 10 xiaohong
}
```

可以发现我们基本上自己实现了`setattr`这个函数，而且这样的实现似乎可以是通用的。只要为特定的类型提供属于它的`fieldInfo`就行了。这个`fieldInfo`里面存了字段名，字段的偏移量，字段的类型大小。它就可以被看做**元信息**,除此之外可能还有变量名，函数名，等等。**这些信息不直接参与程序的运行，而是提供关于程序结构、数据、类型等方面的附加信息**。元信息里面存的东西似乎也都是死套路，对于我们都是已知信息。因为它们就存在程序的源代码里面。那`C/C++`编译器提供这种功能吗？答案是：对于`debug`模式下的程序可能会保留一部分用于程序调试，而在`release`模式下什么都不会存。这样做的好处是很显然的，因为这些信息并不是程序运行起来必须要的信息，不保留它们可以显著减少二进制可执行文件的大小。

## 为什么这些信息是不必要的，什么时候需要？ 

接下来我会以`C`语言为例，将它的源码与二进制表示对应起来。看看执行代码究竟需要哪些信息？

### 变量定义 

```c
int value;
```

事实上变量声明并没有直接对应的二进制表示，它仅仅是告诉编译器需要分配一块空间来存储名为`value`的变量，究竟分配多大的内存则由它的类型决定。所以如果变量声明的时候类型大小是未知的，则会编译错误。

```c
struct A;

A x; // error: storage size of 'x' isn't known
A* y; // ok the size of pointer is always konwn 

struct Node
{
    int val;
    Node next;
}; // error Node is not a complete type
// 其实意思就是定义 Node 类型的时候它的大小还是未知的

struct Node
{
    int val;
    Node* next;
}; // ok
```

相信你想到了这和`malloc`似乎有点像，的确如此。区别在于，`malloc`是在运行时的堆上分配内存。而直接的变量声明一般是在数据区或者栈上分配内存。编译器可能在内部会维护一个符号表，将变量名与它的地址映射起来，在你后续对这个变量进行操作的时候，实际上是对这块内存区域进行操作。

### 内置运算符 

`C`语言内置的运算符一般直接和`CPU`指令直接对应，至于`CPU`是如何实现这些运算的，可以学习下数电相关知识。以`x86_64`为例，可能的对应如下

```c
| Operator | Meaning | Operator | Meaning |
|----------|---------|----------|---------|
| +        | add     | *        | mul     |
| -        | sub     | /        | div     |
| %        | div     | &        | and     |
| \|       | or      | ^        | xor     |
| ~        | not     | <<       | shl     |
| >>       | shr     | &&       | and     |
| ||       | or      | !        | not     |
| ==       | cmp     | !=       | cmp     |
| >        | cmp     | >=       | cmp     |
| <        | cmp     | <=       | cmp     |
| ++       | inc     | --       | dec     |
```

赋值则可能是通过`mov`指令来完成的，比如

```c
a = 3; // mov [addressof(a)] 3
```

### 结构体 

```c
struct Point
{
    int x;
    int y;
}

int main()
{
    Point point;
    point.x = 1;
    point.y = 2;
}
```

结构体的大小一般可以由特定规则算出从它的成员算出，往往要考虑内存对齐，而且是编译器决定的。例如 [msvc](https://learn.microsoft.com/en-us/cpp/c-language/storage-and-alignment-of-structures?view=msvc-170)。但总之在编译的时候结构体的大小就是已知的了，我们也可以通过`sizeof`获取类型或者变量的大小。那么这里的`Point point`变量定义就很好理解，类型大小已知，相对于在栈上分配了一块内存。

下面来关注一下结构体成员访问，事实上`C`语言有一个宏可以获取结构体成员相对于结构体起始地址的偏移量，叫做`offsetof`（就算我们获取不到，编译器里面也是会计算字段偏移量的，所以偏移量信息对编译器总是已知的）。例如在这里`offsetof(Point, x)`就是`0`，`offsetof(Point, y)`就是`4`。所以上面的代码可以理解为

```c
int main()
{
    char point[sizeof(Point)]; // 8 = sizeof(Point)
    *(int*)(point + offsetof(Point, x)) = 1; // point.x = 1
    *(int*)(point + offsetof(Point, y)) = 2; // point.y = 2
}
```

编译器同样可能会维护一个字段名->偏移量的符号表，字段名最终会替换为`offset`。也没有必要在程序中保留了。

### 函数调用 

一般通过函数调用栈实现，这个太常见了，就不仔细说了。函数名最后会直接被替换为函数地址。

### 总结 

通过上面的分析，相信你已经发现了，`C`语言中的符号名，类型名，变量名，函数名，结构体字段名等等信息都被替换成了数字，地址，偏移量等等。缺少了它们对程序运行并没有什么影响。所以选择把它们抛弃掉，减少二进制文件的大小。对于`C++`来说情况基本也是类似的，`C++`只会在一些特殊的情况下保留部分元信息，比如`type_info`，而且可以手动选择关闭掉`RTTI`从而确保不会产生这种信息。

那什么时候我们需要使用这些信息？显然最开始介绍的`setattr`是需要的。在程序调试的时候，我们得知道一个地址对应的变量名，函数名，成员名等等，方便我们调试，这时候我们也是需要的。当把结构体序列化为`json`的时候，我们需要知道它的字段名，我们也需要这些信息。把类型擦除成`void*`了之后，我们还是需要知道它实际对应的类型是什么，这时候我们也是需要的。总之，为了在运行期区分这串二进制内容倒是原本是什么东西的时候，我们就需要这些信息（当然在编译期想要利用这些信息进行代码生成，也是需要的）。

## 如何获取这些信息？ 

`C/C++`编译器并没有提供给我们接口让我们获取这些信息，但是前面已经说了，这些信息显然就在源代码里面啊。变量名，函数名，类型名，字段名。我们可以选择通过人工理解代码，然后手动去存储元信息。几千个类，几十个成员函数，可能写个几个月就好了吧。开玩笑的，或者我们可以写一些程序，比如正则表达式匹配之类的帮我们获取到这些信息？不过，其实我们有更好的选择来获取这些信息，那就是通过`AST`。

## AST(Abstract Syntax Tree) 

`AST`是抽象语法树（`Abstract Syntax Tree`）的缩写。它是编程语言处理中的一种数据结构，用于表示源代码的抽象语法结构。`AST`是源代码经过解析器（`parser`）处理后的结果，它捕捉了代码中的语法结构，但不包含所有细节，比如空白字符或注释。在`AST`中，每个节点代表源代码中的一个语法结构，例如变量声明、函数调用、循环等。这些节点之间通过父子关系和兄弟关系连接，形成了一棵树状结构，这样的结构更容易被计算机程序理解和处理。如果你的电脑里面装了`clang`编译器，可以使用下面这个命令查看一个源文件的语法树

```bash
clang -Xclang -ast-dump -fsyntax-only <your.cpp>
```

输出如下，我筛选出了重要的信息，无关的已经被删除了

```cpp
|-CXXRecordDecl 0x2103cd9c318 <col:1, col:8> col:8 implicit struct Point
|-FieldDecl 0x2103cd9c3c0 <line:4:5, col:9> col:9 referenced x 'int'
|-FieldDecl 0x2103e8661f0 <line:5:5, col:9> col:9 referenced y 'int'
`-FunctionDecl 0x2103e8662b0 <line:8:1, line:13:1> line:8:5 main 'int ()'
  `-CompoundStmt 0x2103e866c68 <line:9:1, line:13:1>
    |-DeclStmt 0x2103e866b30 <line:10:5, col:16>
    | `-VarDecl 0x2103e866410 <col:5, col:11> col:11 used point 'Point':'Point' callinit
    |   `-CXXConstructExpr 0x2103e866b08 <col:11> 'Point':'Point' 'void () noexcept'
    |-BinaryOperator 0x2103e866bb8 <line:11:5, col:15> 'int' lvalue '='
    | |-MemberExpr 0x2103e866b68 <col:5, col:11> 'int' lvalue .x 0x2103cd9c3c0
    | | `-DeclRefExpr 0x2103e866b48 <col:5> 'Point':'Point' lvalue Var 0x2103e866410 'point' 'Point':'Point'
    | `-IntegerLiteral 0x2103e866b98 <col:15> 'int' 1
    `-BinaryOperator 0x2103e866c48 <line:12:5, col:15> 'int' lvalue '='
      |-MemberExpr 0x2103e866bf8 <col:5, col:11> 'int' lvalue .y 0x2103e8661f0
      | `-DeclRefExpr 0x2103e866bd8 <col:5> 'Point':'Point' lvalue Var 0x2103e866410 'point' 'Point':'Point'
      `-IntegerLiteral 0x2103e866c28 <col:15> 'int' 2
```

或者如果你的`vscode`装了`clangd`这个插件，可以右键选择一块代码，然后右键`show AST`来看这块代码片段的`ast`。可以发现上面的确是把源码内容以树的方式呈现给我们了，既然是一颗树，我们就可以自由的遍历树的节点，然后筛选获取我们想要的信息。上面两例都是可视化的输出，通常情况下也会有直接的代码接口来直接获取。比如`python`内置就有`ast`模块来获取，`C++`一般是通过`clang`相关的工具来获取这些内容。如果想知道具体该如何使用`clang`工具，可以参考文章：[使用 clang 工具自由的支配 C++ 代码吧！](https://www.ykiko.me/zh-cn/articles/669360731)

如果你好奇编译器究竟是如何把源代码变成`ast`的，你可以去学习一下编译原理前端的内容。

## 以何种方式存储这些信息？ 

这个问题听起来让人有些困惑，实际上这个问题可能只有`C++`程序员需要考虑

其实一切原因都是`constexpr`引起的。把信息下面这样存储起来

```cpp
struct FieldInfo
{
    std::string_view name;
    std::size_t offset;
    std::size_t size;
}；

struct Point
{
    int x;
    int y;
}；

constexpr std::array<FieldInfo, 2> fieldInfos =
{{
    {"x", offsetof(Point, x), sizeof(int)},
    {"y", offsetof(Point, y), sizeof(int)},
}};
```

就意味着我们不仅仅能在运行期查询这些信息，还能在编译期查询这些信息

更有甚者，还可以存到模板参数里面去，这样的话连类型也能存了

```cpp
template<fixed_string name, std::size_t offset, typename Type>
struct Field{};

using FieldInfos = std::tuple
<
    Field<"x", offsetof(Point, x), int>,
    Field<"y", offsetof(Point, y), int>
>;
```

这样无疑给了我们更大的操作空间，那么有了这些信息之后，下一步该做些什么？事实上我们可以选择基于这部分信息进行代码生成，相关的内容可以浏览系列文章中的其它小节。