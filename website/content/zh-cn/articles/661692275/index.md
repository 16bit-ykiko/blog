---
title: 'C++26 静态反射提案解析'
date: 2023-10-17 02:38:26
updated: 2024-11-30 17:59:18
series: ['Reflection']
series_order: 6
---

最近打算写一个系列文章详细讨论反射（reflection）这一概念，刚好 C++26 有了新的反射提案，发现知乎上又没有相关的文章，而这个话题又经常被讨论。所以借此机会来聊一聊属于 C++ 的静态反射（static reflection），作为系列预热了。

## what is static reflection? 

首先反射是指什么呢？这个词就像计算机科学领域很多其他的惯用词一样，并没有详细而准确的定义。关于这个问题，我不打算在这个文章讨论，后续的文章我会详细的解释。本文的重点是 C++ 的 static reflection，为什么强调 static 呢？主要是因为平常我们谈论到反射的时候几乎总是指 Java，C#，Python 这些语言中的反射，而它们的实现方式无一不是把类型擦除，在运行期进行信息的查询。这种方式当然有不可避免的运行时开销，而这种开销显然是违背了 C++ zero cost abstraction 的原则的。为了和它们的反射区分开来，故加上 static 作为限定词，也指示了 C++ 的反射是在编译期完成的。当然，这种说法仍然缺乏一些严谨性。详细的讨论在后续的文章给出，你只需要知道 C++ 的静态反射和 Java，C#，Python 的反射不同，并且主要是在编译期完成的就行了。

## what can static reflection do? 

### type as value 

我们都知道随着 C++ 版本的不断更新，编译期计算的功能在不断的增强，通过`constexpr/consteval`函数我们能很大程度上直接复用运行期的代码，方便的进行编译期计算。完全取代了很久之前使用模板元进行编译期计算的方法。不仅写起来更加方便，编译速度也更快。

观察下面几段编译期计算阶乘的代码：

在 C++03/98 的时候，我们只能通过模板递归实例化来实现，而且无法将代码复用到运行期

```cpp
template<int N>
struct factorial
{
    enum { value = N * factorial<N - 1>::value };
};

template<>
struct factorial<0>
{
    enum { value = 1 };
};
```

C++11 中第一次引入了`constexpr`函数的概念，使得我们可以编写编译期和运行期复用的代码。但是限制很多，没有变量和循环，我们只能按照纯函数式的风格来编写代码

```cpp
constexpr int factorial(int n) 
{ 
    return n == 0 ? 1 : n * factorial(n - 1); 
}

int main()
{
    constexpr std::size_t a = factorial(5); // 编译期计算
    std::size_t& n = *new std::size_t(6);
    std::size_t b = factorial(n); // 运行期计算
    std::cout << a << std::endl;
    std::cout << b << std::endl;
}
```

随着 C++14/17 的到来，`constexpr`函数中的的限制被进一步放开，现在能在 constexpr 函数中使用局部变量和循环了，就像下面这样

```cpp
constexpr std::size_t factorial(std::size_t N)
{
    std::size_t result = 1;
    for (std::size_t i = 1; i <= N; ++i)
    {
        result *= i;
    }
    return result;
}
```

C++20 之后，我们还可以在编译期使用`new/delete`，我们可以在编译期代码里面使用`vector`。很多运行期的代码可以直接在编译期复用，而不需要任何更改，只需要在函数前面加上一个 constexpr 标记，再也不用为了进行编译期计算而使用晦涩难懂的模板元编程了。但是，上面的示例仅仅适用于 value，在 C++ 里面除了 value 还有 type 和 higher kind type

```cpp
template<typename ...Ts>
struct type_list;

template<typename T, typename U, typename ...Ts>
struct find_first_of
{
    constexpr static auto value = find_first_of<T, Ts...>::value + 1;
};

template<typename T, typename ...Ts>
struct find_first_of<T, T, Ts...>
{
    constexpr static std::size_t value = 0;
};

static_assert(find_first_of<int, double, char, int, char>::value == 2);
```

由于 type 和 higher kind type 只能是 template arguments，所以还是只能通过**模板递归匹配**处理它们。要是我们能像 value 一样操作它们就好了，这样的话 constexpr 函数也能处理它们了。但是 C++ 又不是像 Zig 那样的语言，type is value。怎么办呢？没关系，我们把 type 映射到 value 不就行了？实现 type as value 的效果。在静态反射加入之前，我们可以通过一些 trick 来实现这个效果。可以在编译期把类型映射到类型名，于是只要对类型名进行计算就好了。关于如何进行这种映射，可以参考 [C++ 中如何优雅进行 enum 到 string 的转换](https://www.ykiko.me/zh-cn/articles/680412313)。

```cpp
template<typename ...Ts>
struct type_list{};

template<typename T, typename ...Ts>
constexpr std::size_t find(type_list<Ts...>)
{
    // type_name 用于获取编译期类型名
    std::array arr{ type_name<Ts>()... };
    for(auto i = 0; i < arr.size(); i++)
    {
        if(arr[i] == type_name<T>())
        {
            return i;
        }
    }
}
```

非常直观的代码，但是如果我们想把值映射回类型就比较困难了。不过没关系，在即将到来的 **static reflection** 中，这种类型和值的双向映射已经成为语言特性了，我们不再需要去手动处理了。

使用`^`运算符将类型映射到值

```cpp
constexpr std::meta::info value = ^int;
```

使用`[: ... :]`将它映射回去，注意这是 symbol 级别的映射

```cpp
using Int = typename[:value:]; // 在此语境下，typename 可以省略
typename[:value:] a = 3; // 相当于 int a = 3;
```

现在我们就能写出下面这样的代码了。

```cpp
template<typename ...Ts>
struct type_list
{
    constexpr static std::array types = {^Ts...};

    template<std::size_t N>
    using at = typename[:types[N]:]; 
};

using Second = typename type_list<int, double, char>::at<1>;
static_assert(std::is_same_v<Second, double>);
```

再也不用递归匹配了，我们可以把类型像值一样计算。只要理解了这种映射关系，代码写起来非常简单。用于类型计算的模板元可以退出历史舞台了！

其实`^`其实不仅能够映射类型，主要有下面这些功能: 

- `^::` —— 代表全局命名空间
- `^namespace-name`—— 命名空间名称 
- `^type-id`—— 类型 
- `^cast-expression` —— 特殊表达式，目前包括包括： 
-   - 表示函数或者成员函数的主表达式 
  - 表示变量，静态成员变量，结构化绑定的主表达式 
  - 表示非静态成员的主表达式
  - 表示模板的主表达式 
  - 常量表达式



同样的`[: ... :]`也能还原成对应的东西，注意是还原到对应的符号，所以这个运算符被叫做，拼接器（Splicers）

- `[: r :]` —— 还原成对应的实体或者表达式 
- `typename[: r :]` —— 还原成对应的类型 
- `template[: r :]` —— 还原成模板参数 
- `namespace[: r :]` —— 还原成命名空间 
- `[:r:]::` —— 还原成对应的命名空间，类，枚举嵌套说明符


看下面的使用示例

```cpp
int x = 0;
void g() {
    [:^x:] = 42;     // Okay.  Same as: x = 42;
}
```

如果还原的东西和原本储存的不一样，则会编译错误

```cpp
typename[: ^:: :] x = 0;  // Error
```

### metainfo 

光是上面一个特性，就足以让人心动了。然而远远不止如此，获取`class`等实体元信息的功能也有了。

最基础的，获取类型名（变量名，字段名都可以用这个函数）

```cpp
namespace std::meta 
{
    consteval auto name_of(info r) -> string_view;
    consteval auto display_name_of(info r) -> string_view;
}
```

比如可以

```cpp
display_name_of(^std::vector<int>) //  => std::vector<int>
name_of(^std::vector<int>) // => std::vector<int, std::allocator<int>>
```

判断一个模板是不是另一个高阶模板的特化 和 萃取高阶模板里面的参数

```cpp
namespace std::meta 
{
    consteval auto template_of(info r) -> info;
    consteval auto template_arguments_of(info r) -> vector<info>;
}

std::vector<int> v = {1, 2, 3};
static_assert(template_of(type_of(^v)) == ^std::vector);
static_assert(template_arguments_of(type_of(^v))[0] == ^int);
```

把模板参数填到高阶模板中去

```cpp
namespace std::meta 
{
    consteval auto substitute(info templ, span<info const> args) -> info; 
}

constexpr auto r = substitute(^std::vector, std::vector{^int});
using T = [:r:]; // Ok, T is std::vector<int>
```

获取`struct`,`class`，,`union`,`enum`的成员信息

```cpp
namespace std::meta
{
    template<typename ...Fs>
    consteval auto members_of(info class_type, Fs ...filters) -> vector<info>;

    template<typename ...Fs>
    consteval auto nonstatic_data_members_of(info class_type, Fs ...filters) -> vector<info>
    {
        return members_of(class_type, is_nonstatic_data_member, filters...);
    }

    template<typename ...Fs>
    consteval auto bases_of(info class_type, Fs ...filters) -> vector<info>
    {
        return members_of(class_type, is_base, filters...);
    }

    template<typename ...Fs>
    consteval auto enumerators_of(info class_type, Fs ...filters) -> vector<info>;

    template<typename ...Fs>
    consteval auto subobjects_of(info class_type, Fs ...filters) -> vector<info>;
}
```

待会用这个我们就可以实现遍历结构体，枚举等功能。进一步就可以实现序列化，反序列化等高级功能。后文会有一些示例。除此之外，还有一些其它的功能的编译期函数，上面只展示了一部分内容，更多的 API 可以参考提案中的内容。由于提供了直接获取高级模板里面参数的函数，再也不用用模板去进行类型萃取了！用于类型萃取的模板元也可以退出历史舞台了。

## better compile facilities 

反射的主题部分大致已经介绍完了，现在来聊聊其它的。虽然这部分是其它提案的内容，但是他们可以使代码写起来更见轻松，让代码有更强的表达能力。

### template for 

在 C++ 里面如何生成大量的代码段是一个非常不好解决的问题，得益于 C++ 独（逆）特（天）的机制，目前的代码片段生成几乎都是基于 lambda 表达式 + 可变参数包展开。看下面的例子

```cpp
constexpr auto dynamic_tuple_get(std::size_t N, auto& tuple)
{
    constexpr auto size = std::tuple_size_v<std::decay_t<decltype(tuple)>>;
    [&]<std::size_t ...Is>(std::index_sequence<Is...>)
    {
        auto f = [&]<std::size_t Index>
        {
            if(Index == N)
            {
                std::cout << std::get<Index>(tuple) << std::endl;
            }
        };
        (f.template operator()<Is>(), ...);
    }(std::make_index_sequence<size>{});
}

int main()
{
    std::tuple tuple = {1, "Hello", 3.14, 42};
    auto n1 = 0;
    dynamic_tuple_get(n1, tuple); // 1
    auto n2 = 3;
    dynamic_tuple_get(n2, tuple); // 42
}
```

一个很经典的例子，原理是通过多个分支判断，将运行期变量分发到编译期常量。实现根据运行期的`index`来访问`tuple`里面的元素。**注：这里效率更高的办法是，编译期生成一个函数指针数组，然后直接根据index进行跳转，不过这里只是做个展示，不用纠结太多。**

上面的代码展开后相当于

```cpp
constexpr auto dynamic_tuple_get(std::size_t N, auto& tuple)
{
    if(N == 0)
    {
        std::cout << std::get<0>(tuple) << std::endl;
    }
    // ...
    if(N == 3)
    {
        std::cout << std::get<3>(tuple) << std::endl;
    }
}
```

可以发现，我们用了极其别扭的写法只是为了实现极其简单的效果。而且由于 lambda 其实是个函数，其实没法直接从 lambda 里面直接返回到上一级函数。导致我们多做了很多多余的`if`判断。

换成`template for`则代码看起来清爽很多

```cpp
constexpr void dynamic_tuple_get(std::size_t N, auto& tuple)
{
    constexpr auto size = std::tuple_size_v<std::decay_t<decltype(tuple)>>;
    template for(constexpr auto num : std::views::iota(0, size))
    {
        if(num == N)
        {
            std::cout << std::get<num>(tuple) << std::endl;
            return;
        }
    }
}
```

可以认为`template for`是 lambda 展开的语法糖加强版，反正非常好用就是了。如果这个加入了，利用模板元生成函数（代码）就可以退休了。

### non-transient constexpr allocation 

这个提案主要是将两个问题联合起来讨论了。

- C++ 可以通过控制模板实例化 static 成员在数据段预留位置，可以看作编译期内存分配


```cpp
template<auto... items>
struct make_array
{
    using type = std::common_type_t<decltype(items)...>;
    static inline type value[sizeof ...(items)] = {items...};
};

template<auto... items>
constexpr auto make_array_v = make_array<items...>::value;

int main()
{
    constexpr auto arr = make_array_v<1, 2, 3, 4, 5>;
    std::cout << arr[0] << std::endl;
    std::cout << arr[1] << std::endl; //成功在数据段预留位置，存放的是 1 2 3 4 5
}
```

- C++20 允许了`constexpr`中进行`new`，但是编译期`new`的内存必需要在编译期`delete`。


```cpp
constexpr auto size(auto... Is)
{
    std::vector<int> v = {Is...};
    return v.size();
}
```

那就不能在编译期`new`里之后，不`delete`？实际数据放在数据段？这就是这个提案要解决的问题，它希望我们能使用

```cpp
constexpr std::vector<int> v = {1, 2, 3, 4, 5}; // 全局的
```

主要难点是，在数据段分配的内存不像在堆上的内存一样有所有权，不需要`delete`。只要解决了这个问题，就能使用编译期的`std::map`，`std::vector`并且保留到运行期。这个作者的做法是进行标记。具体的细节这里就不说了。如果这个加入了，利用模板元打常量表也可以退出了。

## some examples 

好了，上面说了那么多，让我们看看用反射我们都能干些什么

### print any type 

```cpp
template<typename T>
constexpr auto print(const T& t)
{
    template for(constexpr auto member : nonstatic_data_members_of(type_of(^t)))
    {
        if constexpr (is_class(type_of(member))) 
        {
            // 如果是 class 就递归遍历成员
            println("{}= ", name_of(member));
            print(t.[:member:]);
        }
        else
        {
            //非类类型可以直接打印
            std::println("{}= {}", name_of(member), t.[:member:]); 
        }
    }
}
```

### enum to string 

```cpp
template <typename E> requires std::is_enum_v<E>
constexpr std::string enum_to_string(E value) 
{
    template for (constexpr auto e : std::meta::members_of(^E)) 
    {
        if (value == [:e:]) 
        {
            return std::string(std::meta::name_of(e));
        }
    }
    return "<unnamed>";
}
```

## conclusion 

花费了很长的篇幅介绍 C++ 的 static reflection。其实我非常喜欢 C++ 的编译期计算，对它的发展史也非常感兴趣。C++ 的编译期计算是一步步摸索出来的，有很多富有智慧的大师提出他们的独特想法，让不可能的事情变成现实。从 C++03 的变态模板元，到 C++11 的`constexpr`变量，到 C++14 ~23 对`constexpr`函数中的限制逐渐放开，把越来越多的操作移到编译期。再到如今的 static reflection，C++ 正在逐步脱离模板元的魔爪。之前那些老旧的模板元写法全都可以淘汰掉了！！！如果你没写过以前的老式模板元代码，大概是体会不到它有多可怕的。

为了让静态反射能早点进入标准，作者团队特地选了原本提案的一部分核心子集。希望如作者所愿，静态反射能在 C++26 进入标准！当然，核心部分先进入，之后再补充更多更加有用的功能，所以这绝不是反射的全部内容。本文只是对该提案的粗略解读和翻译，想要详细了解的还请阅读下方链接中的提案，相关进展持续更新中：

- [Reflection for C++26 - P2996R0](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2023/p2996r0.html)
- [Reflection for C++26 - P2996R1](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2023/p2996r1.html)
- [Reflection for C++26 - P2996R2](https://www.open-std.org/JTC1/SC22/WG21/docs/papers/2024/p2996r2.html)
- [Reflection for C++26 - P2996R3](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2024/p2996r3.html)
- [Reflection for C++26 - P2996R4](https://wg21.link/P2996R4)


实验编译器：

- 在线尝试： [https://godbolt.org/z/13anqE1Pa](https://godbolt.org/z/13anqE1Pa)
- 本地构建： [clang-p2996](https://github.com/bloomberg/clang-p2996.git)


反射系列文章：[写给 C++ 程序员的反射教程](https://www.ykiko.me/zh-cn/articles/669358870)