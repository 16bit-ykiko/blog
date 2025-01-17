---
title: 'The History of constexpr in C++! (Part One)'
date: 2024-02-10 23:15:47
updated: 2024-12-18 11:21:51
series: ['Constexpr']
series_order: 1
---

几个月前，我写了一篇介绍 C++ 模板的文章：[雾里看花：真正意义上的理解 C++ 模板](https://www.ykiko.me/zh-cn/articles/655902377)。

理清了现代 C++ 中模板的地位。其中用 constexpr function 替代模板进行编译期计算可以说是现代 C++ 最重要的改进之一了。 constexpr 本身其实并不难以理解，非常直观。但是由于几乎每个 C++ 版本都在改进它，所以不同的 C++ 版本可以使用的内容差别很大，有时候可能给人一种`inconsistency`的感觉。

刚好最近我偶然间读到了这篇文章：[Design and evolution of constexpr in C++](https://pvs-studio.com/en/blog/posts/cpp/0909/)，全面介绍了 C++ 中 constexpr 的发展史，写的非常好。于是便想将其翻译到中文社区。

但是有趣的是，这篇文章其实也是翻译的。文章的原作者是一位俄罗斯人，文章最初也是发表在俄罗斯的论坛上。这是作者的邮箱：`izaronplatz@gmail.com`，我已经和他联系过了，他回复到：

>  It's always good to spread knowledge in more languages. 

也就是允许翻译了。但是我并不懂俄文，所以主要参考了原文结构，而主体部分，基本都是我重新叙述的。

原文内容较长，故分为上下两篇，这是上篇

## 很神奇吗？ 

constexpr 是当代 C++ 中最神奇的关键字之一。它使得某些代码可以在编译期执行。

随着时间的推移，constexpr 的功能越来越强大。现在几乎可以在编译时计算中使用标准库的所有功能。

constexpr 的发展历史可以追溯到早期版本的 C++。通过研究标准提案和编译器源代码，我们可以了解这一语言特性是如何一步步地构建起来的，为什么会以这样的形式存在，实际上 constexpr 表达式是如何计算的，未来有哪些可能的功能，以及哪些功能可能会存在但没有被纳入标准。

本文适合于任何人，无论你是否了解 constexpr ！

## C++98/03：我比你更 const 

在 C++ 中，有些地方需要整数常量（比如内建数组类型的长度），这些值必须在编译期就确定。C++ 标准允许通过简单的表达式来构造常量，例如

```cpp
enum EPlants{
    APRICOT = 1 << 0,
    LIME = 1 << 1,
    PAPAYA = 1 << 2,
    TOMATO = 1 << 3,
    PEPPER = 1 << 4,
    FRUIT = APRICOT | LIME | PAPAYA,
    VEGETABLE = TOMATO | PEPPER,
};

template <int V>
int foo(int v = 0){
    switch(v){
        case 1 + 4 + 7:
        case 1 << (5 | sizeof(int)):
        case (12 & 15) + PEPPER: return v;
    }
}

int f1 = foo<1 + 2 + 3>();
int f2 = foo<((1 < 2) ? 10 * 11 : VEGETABLE)>();
```

这些表达式在`[expr.const]`小节中被定义，并且被叫做*常量表达式（constant expression）* 。它们只能包含： 

- 字面量：`1`,`'A'`,`true`,`...` 
- 枚举值 
- 整数或枚举类型的模板参数（例如`template<int v>`中的`v`）
- `sizeof`表达式
- 由常量表达式初始化的`const`变量


前几项都很好理解的，对于最后一项稍微有点复杂。如果一个变量具有 [静态储存期](https://en.cppreference.com/w/cpp/language/storage_duration)，那么在常规情况下，它的内存会被填充为`0`，之后在程序开始执行的时候改变。但是对于上述的变量来说，这太晚了，需要在编译结束之前就计算出它们的值。

在 C++98/03 当中有两种类型的 [静态初始化](https://en.cppreference.com/w/cpp/language/initialization#Static_initialization)： 

- [零初始化](https://en.cppreference.com/w/cpp/language/zero_initialization) 内存被填充为`0`，然后在程序执行期间改变 
- [常量初始化](https://en.cppreference.com/w/cpp/language/constant_initialization) 使用常量表达式进行初始化，内存（如果需要的话）立即填充为计算出来的值


> 所有其它的初始化都被叫做 [动态初始化](https://en.cppreference.com/w/cpp/language/initialization#Dynamic_initialization)，这里我们不考虑它们。 

让我们看一个包含两种静态初始化的例子

```cpp
int foo() { return 13; }

const int v1 = 1 + 2 + 3 + 4;              // const initialization
const int v2 = 15 * v1 + 8;                // const initialization
const int v3 = foo() + 5;                  // zero initialization
const int v4 = (1 < 2) ? 10 * v3 : 12345;  // zero initialization
const int v5 = (1 > 2) ? 10 * v3 : 12345;  // const initialization
```

变量`v1`, `v2`和`v5`都可以作为常量表达式，可以用作模板参数，`switch`的`case`，`enum`的值，等等。而`v3`和`v4`则不行。即使我们能明显看出`foo() + 5`的值是`18`，但在那时还没有合适的语义来表达这一点。

由于常量表达式是递归定义的，如果一个表达式的某一部分不是常量表达式，那么整个表达式就不是常量表达式。在这个判断过程中，只考虑实际计算的表达式，所以`v5`是常量表达式，但`v4`不是。

如果没有获取常量初始化的变量的地址，编译器就可以不为它分配内存。所以我们可以通过取地址的方式，来强制编译器给常量初始化的变量预留内存（其实如果没有显式取地址的话，普通的局部变量也可能被优化掉，任何不违背 [as-if](https://en.cppreference.com/w/cpp/language/as_if) 原则的优化都是允许的。可以考虑使用`[[gnu::used]]`这个 attribute 标记避免变量被优化掉）。

```cpp
int main() {
    std::cout << v1 << &v1 << std::endl;
    std::cout << v2 << &v2 << std::endl;
    std::cout << v3 << &v3 << std::endl;
    std::cout << v4 << &v4 << std::endl;
    std::cout << v5 << &v5 << std::endl;
}
```

编译上述代码并查看符号表（环境是 windows x86-64）

```bash
$ g++ --std=c++98  -c main.cpp 
$ objdump -t -C main.o

(sec  6)(fl 0x00)(ty    0)(scl   3) (nx 0) 0x0000000000000000 v1
(sec  6)(fl 0x00)(ty    0)(scl   3) (nx 0) 0x0000000000000004 v2
(sec  3)(fl 0x00)(ty    0)(scl   3) (nx 0) 0x0000000000000000 v3
(sec  3)(fl 0x00)(ty    0)(scl   3) (nx 0) 0x0000000000000004 v4
(sec  6)(fl 0x00)(ty    0)(scl   3) (nx 0) 0x0000000000000008 v5

----------------------------------------------------------------

(sec  3)(fl 0x00)(ty    0)(scl   3) (nx 1) 0x0000000000000000 .bss
(sec  4)(fl 0x00)(ty    0)(scl   3) (nx 1) 0x0000000000000000 .xdata
(sec  5)(fl 0x00)(ty    0)(scl   3) (nx 1) 0x0000000000000000 .pdata
(sec  6)(fl 0x00)(ty    0)(scl   3) (nx 1) 0x0000000000000000 .rdata
```

可以发现在我的 GCC 14 上，零初始化的变量`v3`和`v4`被放在`.bss`段，而常量初始化的变量`v1`, `v2`,`v5`被放在`.rdata`段。操作系统会对`.rdata`段进行保护，使其处于只读模式，尝试写入会导致段错误。

从上述的差异可以看出，一些`const`变量比其它的更加`const`。但是在当时我们并没有办法检测出这种差异（后来的 C++20 引入了 [constinit](https://en.cppreference.com/w/cpp/language/constinit) 来确保一个变量进行常量初始化）。

## 0-∞：编译器中的常量求值器 

为了理解常量表达式是如何求值的，我们需要简单了解编译器的构造。不同编译器的处理方法大致相同，接下来将以 Clang/LLVM 为例

总的来说，编译器可以看做由以下三个部分组成：

- **前端（Front-end）**：将 C/C++/Rust 等源代码转换为 LLVM IR（一种特殊的中间表示）。Clang 是 C 语言家族的编译器前端
- **中端（Middle-end）**：根据相关的设置对 LLVM IR 进行优化
- **后端（Back-end）**：将 LLVM IR 转换为特定平台的机器码： x86/Arm/PowerPC 等等


对于一个简单的编程语言，通过调用 LLVM，`1000`行就能实现一个编译器。你只需要负责实现语言前端就行了，后端交给 LLVM 即可。甚至前端也可以考虑使用 lex/yacc 这样的现成的语法解析器。

具体到编译器前端的工作，例如这里提到的 Clang，可以分为以下三个阶段：

- **词法分析**：将源文件转换为 Token Stream，例如 `[]() { return 13 + 37; }` 被转换为 `[`, `]`, `(`, `)`, `{`, `return`, `13`, `+`, `37`, `;`, `}`
- **语法分析**：产生 Abstract Syntax Tree（抽象语法树），就是将上一步中的 Token Stream 转换为类似于下面这样的递归的树状结构


```bash
lambda-expr 
└── body 
    └── return-expr 
        └── plus-expr 
            ├── number 13
            └── number 37
```

- **代码生成**：根据给定的 AST 生成 LLVM IR


因此，常量表达式的计算（以及相关的事情，如模板实例化）严格发生在 C++ 编译器的前端，而 LLVM 不涉及此类工作。这种处理常量表达式（从 C++98 的简单表达式到 C++23 的复杂表达式）的工具被称为**常量求值器 (constant evaluator)**。

多年来，对常量表达式的限制一直在不断放宽，而 Clang 的常量求值器相应地变得越来越复杂，直到管理 memory model（内存模型）。有一份旧的 [文档](https://clang.llvm.org/docs/InternalsManual.html#constant-folding-in-the-clang-ast)，描述 C++98/03 的常量求值。由于当时的常量表达式非常简单，它们是通过分析语法树进行 *constant folding* （常量折叠）来进行的。由于在语法树中，所有的算术表达式都已经被解析为子树的形式，因此计算常量就是简单地遍历子树。

常量计算器的源代码位于 [lib/AST/ExprConstant.cpp](https://clang.llvm.org/doxygen/ExprConstant_8cpp_source.html)，在撰写本文时已经扩展到将近 17000 行。随着时间的推移，它学会了解释许多内容，例如循环（`EvaluateLoopBody`），所有这些都是在语法树上进行的。

常量表达式与运行时代码有一个重要的区别：它们必须不引发 undefined behavior（未定义行为）。如果常量计算器遇到未定义行为，编译将失败。

```cpp
error: constexpr variable 'foo' must be initialized by a constant expression
    2 | constexpr int foo = 13 + 2147483647;               
      |               ^     ~~~~~~~~~~~~~~~
note: value 2147483660 is outside the range of representable values of type 'int'
    2 | constexpr int foo = 13 + 2147483647;
```

因此在有些时候可以用它们来检测程序中的潜在错误。

## 2003：真的能 macro free 吗？ 

**标准的改变是通过 proposals（提案）进行的**

> 在哪里可以找到提案？它们是由什么组成的？<br><br>所有的有关 C++ 标准的提案都可以在 [open-std.org](https://open-std.org/JTC1/SC22/WG21/) 上找到。它们中的大多数都有详细的描述并且易于阅读。通常由如下部分组成： <br><br>-  当前遇到的问题 <br>-  标准中相关措辞的的链接 <br>-  上述问题的解决方案 <br>-  建议对标准措辞进行的修改 <br>-  相关提案的链接（提案可能有多个版本或者需要和其它提案进行对比） <br>-  在高级提案中，往往还会附带上实验性实现的链接<br><br>可以通过这些提案来了解 C++ 的每个部分是如何演变的。并非存档中的所有提案最终都被接受，但是它们都对 C++ 的发展有着重要的影响。<br><br>通过提交新提案，任何人都可以参与到 C++ 的演变过程中来。 

`2003`年的提案 [N1521 Generalized Constant Expressions](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2003/n1521.pdf) 指出一个问题。如果一个表达式中的某个部分含有函数调用，那么整个表达式就不能是常量表达式，即使这个函数最终能够被常量折叠。这迫使人们在处理复杂常量表达式的时候使用宏，甚至一定程度上导致了宏的滥用

```cpp
inline int square(int x) { return x * x; }
#define SQUARE(x) ((x) * (x))

square(9)
std::numeric_limits<int>::max() 
// 理论上可用于常量表达式, 但是实际上不能

SQUARE(9)
INT_MAX
// 被迫使用宏代替
```

因此，建议引入**常值 (constant-valued)** 函数的概念，允许在常量表达式中使用这些函数。如果希望一个函数是常值函数，那么它必须满足

- inline ，non-recursive，并且返回类型不是 void
- 仅由单一的 return expr 语句组成，并且在把 expr 里面的函数参数替换为常量表达式之后，得到的仍然是一个常量表达式


如果这样的函数被调用，并且参数是常量表达式，那么函数调用表达式也是常量表达式

```cpp
int square(int x) { return x * x; }         // constant-valued
long long_max(int x) { return 2147483647; } // constant-valued
int abs(int x) { return x < 0 ? -x : x; }   // constant-valued
int next(int x) { return ++x; }             // non constant-valued
```

这样的话，不需要修改任何代码，最开始的例子中的`v3`和`v4`也可以被用作常量表达式了，因为`foo`被认为是常值函数。

该提案认为，可以考虑进一步支持下面这种情况

```cpp
struct cayley{
    const int value;
    cayley(int a, int b) : value(square(a) + square(b)) {}
    operator int() const { return value; }
};

std::bitset<cayley(98, -23)> s; // same as bitset<10133>
```

因为成员`value`是`totally constant`的，在构造函数中通过两次调用常值函数进行初始化。换句话说，根据该提案的一般逻辑，此代码可以大致转换为以下形式（将变量和函数移到结构体之外）：

```cpp
// 模拟 cayley::cayley(98, -23)的构造函数调用和 operator int()
const int cayley_98_m23_value = square(98) + square(-23);

int cayley_98_m23_operator_int() { return cayley_98_m23_value; }

// 创建 bitset
std::bitset<cayley_98_m23_operator_int()> s; // same as bitset<10133>
```

但是和变量一样，程序员无法确定一个函数是否为常值函数，只有编译器知道。

> 提案通常不会深入到编译器实现它们的细节。上述提案表示，实现它不应该有任何困难，只需要稍微改变大多数编译器中存在的常量折叠即可。然而，提案与编译器实现密切相关。如果提案无法在合理时间内实现，很可能不会被采纳。从后来的视角来看，许多大的提案最后被分成了多个小的提案逐步实现 

## 2006-2007：当一切浮出水面 

幸运的是，三年后，这个提案的后续修订版 [N2235](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2007/n2235.pdf) 认识到了过多的隐式特性是不好的，程序员应该有办法确保一个变量可以被用作常量，如果不满足相应的条件应该导致编译错误。

```cpp
struct S{
    static const int size;
};

const int limit = 2 * S::size;                 // dynamic initialization
const int S::size = 256;                       // const initialization
const int z = std::numeric_limits<int>::max(); // dynamic initialization
```

根据程序员的设想，`limit`应该被常量初始化，但事实并非如此，因为`S::size`被定义在`limit`之后，定义的太晚了。可以通过 C++20 加入的 [constinit](https://en.cppreference.com/w/cpp/language/constinit) 来验证这一点，`constinit`保证一个变量进行常量初始化，如果不能进行常量初始化，则会编译错误。

在新的提案中，常值函数被**重命名**为 *constexpr function* ，对它们的要求保持不变。但现在，为了能够在常量表达式中使用它们，**必须**使用 constexpr 关键字进行声明。此外，如果函数体不符合相关的要求，将会编译失败。同时建议将一些标准库的函数（如`std::numeric_limits`中的函数）标记为 constexpr，因为它们符合相关的要求。**变量**或类成员也可以声明为 constexpr，这样的话，如果变量不是通过常量表达式进行初始化，将会编译失败。

用户自定义`class`的 constexpr 构造函数也合法化了。该构造函数必须具有空函数体，并用常量表达式初始化成员。隐式生成的构造函数将尽可能的被标记为 constexpr。对于 constexpr 的对象，析构函数必须是平凡的，因为非平凡的析构函数通常会在正在执行的程序上下文中做一些改变，而在 constexpr 计算中不存在这样的上下文。

以下是包含 constexpr 的示例类：

```cpp
struct complex {
    constexpr complex(double r, double i) : re(r), im(i) { }

    constexpr double real() { return re; }
    constexpr double imag() { return im; }

private:
    double re;
    double im;
};

constexpr complex I(0, 1); // OK
```

在提案中，像`I`这样的对象被称为用户自定义字面量。"字面量" 是 C++ 中的基本实体。就像 "简单" 字面量（数字、字符等）立即被嵌入到汇编指令中，字符串字面量存储在类似`.rodata`的段中那样，用户定义的字面量也在其中占有一席之地。

现在 constexpr 变量不仅可以是数字和枚举，还可以是 [literal type](https://en.cppreference.com/w/cpp/named_req/LiteralType)，在此提案中引入了（尚不支持引用类型）。literal type 是可以传递给 constexpr 函数的类型，这些类型足够简单，以至于编译器可以在常量计算中支持它们。

constexpr 关键字最后成为了一个 *specifier（说明符* ），类似于 *override * 这样仅用作标记。在讨论后，决定不创建新的 [储存期类型](https://en.cppreference.com/w/cpp/language/storage_duration) 和新的类型限定符，并且也决定不允许将其用于函数参数，以免使得函数的[overload resolution](https://en.cppreference.com/w/cpp/language/overload_resolution)规则变得过于复杂。

## 2007：试着让标准库更加 constexpr？ 

在这一年，提案 [N2349 Constant Expressions in the Standard Library](https://open-std.org/JTC1/SC22/WG21/docs/papers/2007/n2349.pdf) 被提出，其中标记了一些函数和常量为   constexpr，还有一些容器的函数，例如：

```cpp
template<size_t N>
class bitset{
    // ...
    constexpr bitset();
    constexpr bitset(unsigned long);
    // ...
    constexpr size_t size();
    // ...
    constexpr bool operator[](size_t) const;
};
```

构造函数通过 constant-expression 初始化类的成员，其他函数内部含有单个 return 语句，符合当前的规定。

所有关于 constexpr 的提案中，超过一半是建议将标准库中的某些函数标记为 constexpr。就内容而言，其实并不是十分有趣，因为它们并没有导致核心语言规则的改变。

## 2008年：停停...机问题？我才不管！ 

```cpp
constexpr unsigned int factorial(unsigned int n){
    return n == 0 ? 1 : n * factorial(n - 1);
}
```

最初，提案提出者希望允许在 constexpr 函数中进行递归调用，但出于谨慎起见，这一做法被禁止了。然而，在审查过程中，由于措辞的变化，意外地允许了这种做法。CWG 认为递归具有足够的使用情景，因此应该允许它们。如果允许函数之间相互递归调用，还需要允许 constexpr 函数的 *forward declaration（向前声明）* 。在 constexpr 函数中调用未定义的 constexpr 函数时，应该在需要常量求值的上下文中进行诊断。这一点在 [N2826](https://open-std.org/JTC1/SC22/WG21/docs/papers/2009/n2826.html) 被澄清

既然有递归，那就可能出现无穷递归。一个函数究竟会不会无穷递归？在一些简单的情况下，静态分析工具可以分析无穷递归是否会发生。而在一般情况下，这其实是个 [停机问题](https://en.wikipedia.org/wiki/Halting_problem)，无法解决。

一般来说，编译器会设置一个默认递归层数。如果递归层数超过这个默认的层数，则会编译错误

```cpp
constexpr int foo(){ return f() + 1; }
constexpr int x = foo();
```

上述代码编译错误

```bash
error: 'constexpr' evaluation depth exceeds maximum of 512 
    (use '-fconstexpr-depth=' to increase the maximum)
   24 |     constexpr int x = foo();
```

在 Clang 中默认的层数是 512，可以通过`-fconstexpr-depth`来修改，其实模板实例化也会有类似的层数限制。从效果上而言，这个限制可以看成类似运行时函数调用的栈大小，超过这个大小就会“爆栈”了，其实也是挺合理的。

## 2010：引用还是指针？ 

当时，许多函数都无法被标记为 constexpr，因为它们的参数中含有引用。

```cpp
template <class T> 
constexpr const T& max(const T& a, const T& b); // error

constexpr pair();               // ok
pair(const T1& x, const T2& y); // error
```

提案 [N3039 Constexpr functions with const reference parameters](https://open-std.org/JTC1/SC22/WG21/docs/papers/2010/n3039.pdf) 希望允许函数参数和返回值出现常量引用。

事实上，这是个非常巨大的改变。在此之前，常量求值中只有**值**，没有引用（指针）。只需要简单的对值进行运算就行了，引用的引入让常量求值器不得不建立一个内存模型。如果要支持`const T&`，编译器需要在编译期创建一个临时对象，然后将引用绑定到它上面。任何对该对象不合法的访问都应该导致编译错误。

```cpp
template <typename T>
constexpr T self(const T& a) { return *(&a); }

template <typename T>
constexpr const T* self_ptr(const T& a) { return &a; }

template <typename T>
constexpr const T& self_ref(const T& a) { return *(&a); }

template <typename T>
constexpr const T& near_ref(const T& a) { return *(&a + 1); }

constexpr auto test1 = self(123); // OK
constexpr auto test2 = self_ptr(123); // 失败，指向临时对象的指针不是常量表达式

constexpr auto test3 = self_ref(123); // OK
constexpr auto tets4 = near_ref(123); // 失败，指针越界访问
```

## 2011：为什么不能有声明？ 

前文提到过，constexpr 函数只能由单个 return 语句构成。这就意味着，里面甚至不允许任何不影响求值的声明。但是至少有三种声明有助于编写此类函数：静态断言，类型别名和常量表达式初始化的局部变量

```cpp
constexpr int f(int x){
    constexpr int magic = 42;
    return x + magic; // should be ok
}
```

提案 [N3268 static_assert and list-initialization in constexpr functions](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2011/n3268.htm) 希望在 constexpr 函数中支持这些静态声明。

## 2012：我需要分支！ 

有许多简单的函数，希望能够在编译时计算，例如计算`a`的`n`次方：

```cpp
int pow(int a, int n){
    if (n < 0)
        throw std::range_error("negative exponent for integer power");

    if (n == 0)
        return 1;

    int sqrt = pow(a, n / 2);
    int result = sqrt * sqrt;

    if (n % 2)
        return result * a;

    return result;
}
```

然而，在当时（C++11），为了它能够变成 constexpr 的，程序员需要按照纯函数式风格（没有局部变量和循环）写一份全新的代码

```cpp
constexpr int pow_helper(int a, int n, int sqrt) { 
    return sqrt * sqrt * ((n % 2) ? a : 1); 
}

constexpr int pow(int a, int n){
    return (n < 0)
               ? throw std::range_error("negative exponent for integer power")
               : (n == 0)
                     ? 1
                     : pow_helper(a, n, pow(a, n / 2));
}
```

提案 [N3444 Relaxing syntactic constraints on constexpr functions](https://open-std.org/JTC1/SC22/WG21/docs/papers/2012/n3444.html) 希望进一步放宽 constexpr 函数的限制，以便能够编写任意的代码 

- 允许声明具有 [literal type](https://en.cppreference.com/w/cpp/named_req/LiteralType) 类型的局部变量，如果它们是通过构造函数进行初始化的，则该构造函数也必须被标记为 constexpr。这样，常量求值器可以缓存这些变量，避免重复求值相同的表达式，提高常量求值器的执行效率，但是不允许修改这些变量 
- 允许局部类型声明 
- 允许使用`if`和多个`return`语句，并且要求每个分支至少有一个`return`语句
- 允许 expression statement（仅由表达式构成的语句） 
- 允许静态变量的地址或引用作为常量表达式


```cpp
constexpr mutex& get_mutex(bool which){
    static mutex m1, m2;
    if (which)
        return m1;
    else
        return m2;
}

constexpr mutex& m = get_mutex(true); // OK
```

但是，不允许`for/while`循环，`goto`，`switch`，`try`，这些可能产生复杂控制流，甚至产生无穷循环的语句。

## 2013：小孩子才做选择，循环我也要！ 

然而，CWG 认为在 constexpr 函数中支持循环（至少支持`for`）是必须的。`2013`年提案  [Relaxing constraints on constexpr functions](https://open-std.org/JTC1/SC22/WG21/docs/papers/2013/n3597.html) 发布了修订版本。

实现 constexpr for 考虑了四种选项。

- 添加全新的循环语法，新语法与 constexpr 所需的函数式编程风格良好交互。虽然解决了缺乏循环的问题，但并未消除程序员对现有语言的不满（为了支持 constexpr，需要将原有的代码重新改写）
- 仅支持传统 C 语言风格的 for 循环，为此，至少需要支持 constexpr 函数中对变量进行更改
- 仅支持 [range-based for loop](https://en.cppreference.com/w/cpp/language/range-for)，这样的循环不能与用户定义的迭代器类型一起使用，除非进一步放宽语言规则
- 允许在 constexpr 函数中使用 C++ 的一致和广泛的子集，可能包括所有 C++


最后选择的是最后一个选项，这极大的影响了 constexpr 在 C++ 中的后续发展。

为了支持这个选项，我们不得不在 constexpr 函数中引入变量的可变性，即支持修改变量的值。根据该提案，现在可以更改在常量求值过程中创建的对象，直到求值过程或对象的 [lifetime](https://en.cppreference.com/w/cpp/language/lifetime) 结束。这些求值过程将在类似虚拟机的沙箱中进行，不会影响外部的代码。因此理论上，输出相同的 constexpr 参数将会输出相同的结果。

```cpp
constexpr int f(int a){
    int n = a;
    ++n; // ++n 不是一个常量表达式
    return n * a;
}

int k = f(4);
// OK，这是一个常量表达式
// f 中的 n 可以被修改，因为其生存期
// 在表达式求值期间开始

constexpr int k2 = ++k;
// 错误，不是一个常量表达式，不能修改 k
// 因为其生存期没有在，这个表达式内开始

struct X{
    constexpr X() : n(5){
        n *= 2; // 不是一个常量表达式
    }
    int n;
};

constexpr int g(){
    X x; // x 的初始化是一个常量表达式
    return x.n;
}

constexpr int k3 = g();
//  OK，这是一个常量表达式
//  x.n 可以被修改，因为
//  x 的生存期在 g() 的求值期间开始
```

另外，我想指出现在这样的代码也能编译通过：

```cpp
constexpr void add(X& x) { x.n++; }

constexpr int g(){
    X x;
    add(x);
    return x.n;
}
```

常量求值中，局部的副作用也是允许的！

## 2013：constexpr 不是 const 的子集！ 

目前，类的 constexpr 函数会自动标记为 const 

在提案 [constexpr member functions and implicit const](https://open-std.org/JTC1/SC22/WG21/docs/papers/2013/n3598.html) 中指出：如果一个成员函数是 constexpr 的，它不一定一定要是 const 的。随着 constexpr 计算中的可变性变得越来越重要，这一点变得更加突出。但即使在此之前，它也妨碍了在 constexpr 和非 constexpr 代码中使用相同的函数：

```cpp
struct B{
    A a;
    constexpr B() : a() {}
    constexpr const A& getA() const /*implicit*/ { return a; }
    A& getA() { return a; } // 代码重复
};
```

有趣的是，提案提供了三个选项，其中选择了第二个：

- 维持现状 -> 导致代码重复
- 被 constexpr 标记的函数不是隐式 const 的 -> 破坏 ABI，成员函数的 const 签名是函数类型的一部分
- 使用`mutable`进行标记`constexpr A &getA() mutable { return a; };`  -> 更加不协调了


最终，方案`2`被接受了，现在如果一个成员函数被 constexpr 标记，不代表它是隐式 const 的成员函数了。 

---

下篇在这里：[C++ 中 constexpr 的发展史（下）](https://www.ykiko.me/zh-cn/articles/683463723)。