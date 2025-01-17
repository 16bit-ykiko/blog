---
title: 'Comprehensive Analysis of C++ Member Pointers'
date: 2023-10-04 14:50:12
updated: 2024-12-18 11:24:06
---

## 引言

在 C++ 中，形如`&T::name`的表达式返回的结果就是成员指针。写代码的时候偶尔会用到，但是这个概念可能很多人都并不熟悉。考虑如下代码

```cpp
struct Point {
    int x;
    int y;
};

int main() {
    Point point;
    *(int*)((char*)&point + offsetof(Point, x)) = 20;
    *(int*)((char*)&point + offsetof(Point, y)) = 20;
}
```

在 C 语言中，我们经常通过这样计算 offset 的方式来访问结构体成员。如果把它封装成函数，还能用来根据传入的参数动态访问结构体的成员变量。然而上面的代码在 C++ 中是 undefined behavior，具体的原因可以参考 [Stack Overflow](https://stackoverflow.com/questions/66800315/can-i-manually-access-fields-by-their-raw-offset-in-c) 上的这个讨论。但是如果我们确实有这样需求，那该怎么合法的实现需求呢？C++ 为我们提供了一层抽象：[pointers to members](https://en.cppreference.com/w/cpp/language/pointer#Pointers_to_members)，用来合法进行这样的操作。

## 使用

### 指向数据成员的指针

一个指向类`C`非静态成员`m`的成员指针可以用`&C::m`进行初始化。当在`C`的成员函数里面使用`&C::m`会出现二义性。即既可以指代对`m`成员取地址`&this->m`，也可以指代成员指针。为此标准规定，`&C::m`表示成员指针，`&(C::m)`或者`&m`表示对`m`成员取地址。可以通过运算符`.*`和`->*`来访问对应的成员。示例代码如下

```cpp
struct C {
    int m;

    void foo() {
        int C::*x1 = &C::m;  // pointer to member m of C
        int* x2 = &(C::m);   // pointer to member this->m
    }
};

int main() {
    int C::*p = &C::m;
    // type of a member pointer is: T U::*
    // T is the type of the member, U is the class type
    // here, T is int, U is C

    C c = {7};
    std::cout << c.*p << '\n';  // same as c.m, print 7

    C* cp = &c;
    cp->m = 10;
    std::cout << cp->*p << '\n';  // same as cp->m, print 10
}
```

- 指向基类的数据成员指针 可以隐式转换成 **非虚继承 **的派生类数据成员指针


```cpp
struct Base {
    int m;
};

struct Derived1 : Base {};  // non-virtual inheritance

struct Derived2 : virtual Base {};  // virtual inheritance

int main() {
    int Base::*bp = &Base::m;
    int Derived1::*dp = bp;   // ok, implicit cast
    int Derived2::*dp2 = bp;  // error

    Derived1 d;
    d.m = 1;
    std::cout << d.*dp << ' ' << d.*bp << '\n';  // ok, prints 1 1
}
```

- 根据传入的指针，动态访问结构体字段


```cpp
struct Point {
    int x;
    int y;
};

auto& access(Point& point, auto pm) { return point.*pm; }

int main() {
    Point point;
    access(point, &Point::x) = 10;
    access(point, &Point::y) = 20;
    std::cout << point.x << ' ' << point.y << '\n';  // 10 20
}}
```

### 指向成员函数的指针

一个指向非静态成员函数`f`的成员指针可以用`&C::f`进行初始化。由于不能对非静态成员函数取地址，`&(C::f)`和`&f`什么都不表示。类似的可以通过运算符`.*`和`->*`来访问对应的成员函数。如果成员函数是重载函数，想要获取对应的成员函数指针，请参考 [如何获取重载函数的地址](https://en.cppreference.com/w/cpp/language/overloaded_address)。示例代码如下

```cpp
struct C {
    void foo(int x) { std::cout << x << std::endl; }
};

int main() {
    using F = void(int);         // function type
    using MP = F C::*;           // pointer to member function
    using T = void (C::*)(int);  // pointer to member function
    static_assert(std::is_same_v<MP, T>);

    auto mp = &C::foo;
    T mp2 = &C::foo;
    static_assert(std::is_same_v<decltype(mp), T>);

    C c;
    (c.*mp)(1);  // call foo, print 1

    C* cp = &c;
    (cp->*mp)(2);  // call foo, print 2
}
```

- 指向基类的成员函数指针 可以隐式转换成 **非虚继承 **的派生类成员函数指针


```cpp
struct Base {
    void f(int) {}
};

struct Derived1 : Base {};  // non-virtual inheritance

struct Derived2 : virtual Base {};  // virtual inheritance

int main() {
    void (Base::*bp)(int) = &Base::f;
    void (Derived1::*dp)(int) = bp;   // ok, implicit cast
    void (Derived2::*dp2)(int) = bp;  // error
    Derived1 d;
    (d.*dp)(1);  // ok
}
```

- 根据传入参数动态调用成员函数


```cpp
struct C { 
    void f(int x) { std::cout << x << std::endl;} 
    void g(int x) { std::cout << x + 1 << std::endl;}
};

auto access(C& c, auto pm, auto... args){
    return (c.*pm)(args...);
}

int main(){
    C c;
    access(c, &C::f, 1); // 1
    access(c, &C::g, 1); // 2
}
```

## 实现

首先要明确的是，C++ 标准并没有规定成员指针是什么实现的。在这一点上和虚函数一样，即标准没有规定虚函数是怎么实现的，只规定了虚函数的行为。所以成员指针相关的实现完全是 **implementation defined**。本来只需要了解怎么使用就足够了，不要关心底层实现。但是奈何网络上相关话题的错误文章太多了，已经严重的产生了误导，所以有必要进行澄清。

对于三大主流编译器，GCC 遵循 Itanium C++ ABI ，MSVC 则遵守 MSVC C++ ABI，Clang 通过不同的编译选项可以分别设置为这两种 ABI。关于 ABI 的详细讨论请移步 [彻底理解 C++ ABI](https://www.ykiko.me/zh-cn/articles/692886292) 和 [MSVC 与 GCC 产生的动态库如何才能相互替换](https://www.zhihu.com/question/653778109/answer/3480007666)，这里不过多介绍。

- [Itanium ABI](https://itanium-cxx-abi.github.io/cxx-abi/abi.html#data-member-pointers) 具有公开的文档，之后的相关描述主要参考这个文档
- MSVC ABI 没有公开的文档，之后的相关描述主要参考 [MSVC C++ ABI Member Function Pointers](https://rants.vastheman.com/2021/09/21/msvc/) 这篇博客


**请注意：文章具有时效性，未来的实现可能会改变，仅作参考，以官方文档为准。**

首先尝试打印一个成员指针的值

```cpp
struct C { 
    int m;
    void foo(int x) { std::cout << x << std::endl;} 
};

int main(){
    int C::* p = &C::m;
    void (C::* p2)(int) = &C::foo;
    std::cout << p << std::endl;  // 1
    std::cout << p2 << std::endl; // 1
}
```

输出的结果都是`1`。鼠标移到`<<`就会发现，这是发生了到`bool`的隐式类型转换。`<<`并没有重载成员指针类型。我们只能通过一些手段查看它的二进制值表示。

## Itanium C++ ABI 

### 指向数据成员的指针

一般来说可以用下述结构体表示，数据成员指针。表示相对于对象首地址的偏移量。如果是`nullptr`则里面存的是`-1`。此时成员指针大小就是`sizeof(ptrdiff_t)`。

```cpp
struct data_member_pointer{ 
    ptrdiff_t offset; 
};
```

如前文所述，C++ 标准不允许沿着虚继承链进行成员指针转换。所以在编译期根据继承关系就可以算出转换需要的 offset，而不需要在运行期去查虚表。

```cpp
struct A {
    int a;
};

struct B {
    int b;
};

struct C : A, B {};

void log(auto mp) {
    std::cout << "offset is "
              << *reinterpret_cast<ptrdiff_t*>(&mp)
              // or use std::bit_cast after C++20
              // std::bit_cast<std::ptrdiff_t>(mp)
              << std::endl;
}

int main() {
    auto a = &A::a;
    log(a);  // offset is 0
    auto b = &B::b;
    log(b);  // offset is 0

    int C::*c = a;
    log(c);  // offset is 0
    // implicit cast
    int C::*c2 = b;
    log(c2);  // offset is 4
}
```

### 指向成员函数的指针

在主流的平台上，一般来说可以用下述结构体表示，成员函数指针:

```cpp
struct member_function_pointer {
    std::ptrdiff_t ptr;  // function address or vtable offset
    // if low bit is 0, it's a function address, otherwise it's a vtable offset
    ptrdiff_t offset;  // offset to the base(unless multiple inheritance, it's always 0)
};
```

这个实现依赖于一些大多数平台的假定： 

- 考虑到地址对齐，**非静态成员函数的地址**最低位几乎总是 0 
- 空的函数指针是 0，所以**空函数指针**可以和**虚表偏移量**区分开来
- 体系结构是字节寻址，并且指针大小是偶数，所以**虚表偏移量是偶数**
- 只要知道虚表的地址，虚表偏移量和函数类型就可以进行函数调用，具体的实现细节由编译器根据 ABI 来决定 


当然也有一些平台不满足上述假设，例如 ARM32 平台的某些情况，这时候它的实现方式就和我们刚才说的不同了。所以你现在应该能更加理解什么叫实现定义的行为了，即使编译器相同，但是目标平台不同，实现都有可能不同。

在我的环境 x64 windows 上，符合主流实现的要求。于是对着这个 ABI，进行了"解糖"。

```cpp
struct member_func_pointer {
    std::size_t ptr;
    ptrdiff_t offset;
};

template <typename Derived, typename Ret, typename Base, typename... Args>
Ret invoke(Derived& object, Ret (Base::*ptr)(Args...), Args... args) {
    Ret (Derived::*dptr)(Args...) = ptr;
    member_func_pointer mfp = *(member_func_pointer*)(&dptr);
    using func = Ret (*)(void*, Args...);

    void* self = (char*)&object + mfp.offset;
    func fp = nullptr;
    bool is_virtual = mfp.ptr & 1;

    if(is_virtual) {
        auto vptr = (char*)(*(void***)self);
        auto voffset = mfp.ptr - 1;
        auto address = *(void**)(vptr + voffset);
        fp = (func)address;
    } else {
        fp = (func)mfp.ptr;
    }

    return fp(self, args...);
}

struct A {
    int a;

    A(int a) : a(a) {}

    virtual void foo(int b) { std::cout << "A::foo " << a << b << std::endl; }

    void bar(int b) { std::cout << "A::bar " << a << b << std::endl; }
};

int main() {
    A a = {4};
    invoke(a, &A::foo, 3);  // A::foo 43
    invoke(a, &A::bar, 3);  // A::bar 43
}
```

## MSVC C++ ABI 

MSVC 对于此的实现非常复杂，还对 C++ 标准进行了扩展。如果想要细致全面的了解，还是建议阅读上面那篇博客。

C++ 标准不允许虚基类成员指针向子类成员指针转换，但是 MSVC 允许。

```cpp
struct Base {
    int m;
};

struct Derived1 : Base {};  // non-virtual inheritance

struct Derived2 : virtual Base {};  // virtual inheritance

int main() {
    int Base::*bp = &Base::m;
    int Derived1::*dp = bp;   // ok, implicit cast
    int Derived2::*dp2 = bp;  // ok in MSVC， error in GCC
}
```

为了不浪费空间，即使在同一程序中 MSVC 的成员指针大小也可能是不同的大小（Itanium 中由于统一实现，所以都是一样大的）。MSVC 对不同情况做了不同处理。

> 另外请注意 MSVC 对于虚继承的是实现和 Itanium 也是不一样的。可以参考 [C++中虚函数、虚继承内存模型](https://zhuanlan.zhihu.com/p/41309205) 这篇文章中的相关介绍。 

### 指向数据成员的指针

对于非虚继承的情况下，实现的和 GCC 类似。除了大小有点区别。`64`位程序中 GCC 是`8`字节，MSVC 是`4`字节。都是用`-1`表示`nullptr`。

```cpp
struct data_member_pointer { 
    int offset; 
};
```

对于虚继承的情况下（标准扩展），需要额外存储一个 voffset。用于运行期从虚表里面找到对应虚基类成员的 offset。

```cpp
struct Base {
    int m;
};

struct Base2 {
    int n;
};

struct Base3 {
    int n;
};

struct Derived : virtual Base, Base2, Base3 {};

struct dmp {
    int offset;
    int voffset;
};

template <typename T>
void log(T mp) {
    dmp d = *reinterpret_cast<dmp*>(&mp);
    std::cout << "offset is " << d.offset << ", voffset is " << d.voffset << std::endl;
}

int main() {
    int Derived::*dp = &Base::m;
    log(dp);  // offset is 0, voffset is 4
    dp = &Base3::n;
    log(dp);  // offset is 4, voffset is 0
}
```

### 指向成员函数的指针

对于成员函数指针就更复杂了，有四种情况： 

- 非虚继承，非多继承


```cpp
struct member_function_ptr{ 
    void* address; 
};
```

- 非虚继承，多继承


```cpp
struct member_function_ptr{ 
    void* address;
    int offset;
};
```

- 虚继承，多继承


```cpp
struct member_function_ptr{ 
    void* address; 
    int offset;
    int vindex;
};
```

- 未知继承


```cpp
struct member_function_ptr{
    void*   address; 
    int     offset;
    int     vadjust; // use to find vptr 
    int     vindex; 
};
```

还要注意：`32`程序中成员函数的调用约定和普通函数不一样。所以如果希望转换成函数指针并调用，需要在函数指针里面把函数调用约定写上才行，不然会导致调用失败。 

## 结论

讨论 C++ 问题千万不要想当然，你在特定平台上的测试结果，不代表所有可能的实现。而且 MSVC 已经告诉你了，即使是同一个程序内，你的测试也可能没有覆盖到所有的 case。之前发现 MSVC 的成员函数指针大小变来变去的时候给我吓了一跳，以为是我的代码出了问题。如果希望自己写一个类似`std::function`的容器，并希望执行 SBO 优化，最好把 SBO 大小设置在`16`字节以上，这样能覆盖掉绝大部分的成员函数指针。 

如果需要成员函数作为回调函数的，推荐使用 lambda 表达式包裹一层。 像下面这样

```cpp
struct A {
    int a;

    void bar(int b) { std::cout << "A::bar " << a << b << std::endl; }
};

int main() {
    auto f = +[](A& a, int b) { a.bar(b); };
    // + is unary plus operator, use to cast a non-capturing lambda to a function pointer
    // f is function pointer
}
```

在 C++23 之后，如果使用 [explicit this](https://en.cppreference.com/w/cpp/language/member_functions#Explicit_object_member_functions) 定义成员函数，则`&C::f`可以直接获取对应成员函数的函数指针，不需要像上面那样多一层包裹了 

```cpp
struct A {
    void bar(this A& self, int b);
};

auto p = &A::bar;
// p is function pointer, rather than member function pointer
```