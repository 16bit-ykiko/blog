---
title: 'Python 与 C++ 的完美结合：pybind11 中的对象设计'
date: 2024-06-07 15:28:11
updated: 2024-12-02 21:20:31
---

参加了 [Google Summer of Code 2024](https://summerofcode.withgoogle.com/programs/2024/projects/Ji2Mi97o)，主要的任务就是为一个 [Python 解释器](https://pocketpy.dev/) 实现 [pybind11](https://github.com/pybind/pybind11) 的兼容性接口。说是实现兼容性接口，实际上相当于重写 pybind11 了，所以最近一直在读它的源码。

>  可能有的读者不太清楚 pybind11 是什么，简单来说 pybind11 是一个中间件，让你可以方便进行 Python 与 C++ 代码之间的交互。比如在 C++ 中内嵌 Python 解释器，或者把 C++ 代码编译成动态库以供 Python 调用。具体的内容还请见官方文档。 

最近基本把框架的大体的运作逻辑理清了。现在回过头来看，pybind11 不愧是 C++ 和 Python 绑定的事实标准，有很多巧妙的设计。它这套交互逻辑也完全可以套用到 C++ 和其它有 GC 的语言的交互上，比如 JS 和 C#（虽然现在并没有 jsbind11 和 csharpbind11 之类的东西）。最近可能我会写一系列相关的文章，去掉一些繁琐的细节，介绍其中一些共用的思想。

这篇文章主要是讨论 pybind11 对象设计一些有意思的点。

## PyObject 

我们都知道 Python 中，一切皆对象，全都是`object`。但是 pybind11 实际上是需要和 CPython 这种 Python 的具体实现打交道的。那一切皆对象在 CPython 中的体现是什么呢？答案是`PyObject*`。接下来让我们“看见” Python，理解实际的 Python 代码是如何运作在 CPython 中的。

创建一个对象实际上就是创建一个`PyObject*`

```python
x = [1, 2, 3]
```

CPython 中有专门的 API 来创建内建类型的对象，上面这句话大概就会被翻译成

```c
PyObject* x = PyList_New(3);
PyList_SetItem(x, 0, PyLong_FromLong(1));
PyList_SetItem(x, 1, PyLong_FromLong(2)); 
PyList_SetItem(x, 2, PyLong_FromLong(3));
```

这样的话，`is`的作用就很好理解了，就是用来判断两个指针的值是否相同。而所谓的默认浅拷贝的原因也就是因为默认的赋值只是指针的赋值，不涉及它指向的元素。

CPython 也提供了一系列的 API 用来操作 `PyObject*` 指向的对象，例如

```cpp
PyObject* PyObject_CallObject(PyObject *callable_object, PyObject *args);
PyObject* PyObject_CallFunction(PyObject *callable_object, const char *format, ...);
PyObject* PyObject_CallMethod(PyObject *o, const char *method, const char *format, ...);
PyObject* PyObject_CallFunctionObjArgs(PyObject *callable, ...);
PyObject* PyObject_CallMethodObjArgs(PyObject *o, PyObject *name, ...);
PyObject* PyObject_GetAttrString(PyObject *o, const char *attr_name);
PyObject* PyObject_SetAttrString(PyObject *o, const char *attr_name, PyObject *v);
int PyObject_HasAttrString(PyObject *o, const char *attr_name);
PyObject* PyObject_GetAttr(PyObject *o, PyObject *attr_name);
int PyObject_SetAttr(PyObject *o, PyObject *attr_name, PyObject *v);
int PyObject_HasAttr(PyObject *o, PyObject *attr_name);
PyObject* PyObject_GetItem(PyObject *o, PyObject *key);
int PyObject_SetItem(PyObject *o, PyObject *key, PyObject *v);
int PyObject_DelItem(PyObject *o, PyObject *key);
```

这些函数在 Python 中基本都有直接对应，看名字就知道是干什么用的了。

## handle 

由于 pybind11 要支持在 C++ 中操作 Python 对象，首要任务就是对上述这些 C 风格的 API 进行封装。具体是由`handle`这个类型来完成的。`handle`是对`PyObject*`的简单包装，并且封装了一些成员函数，例如

大概像下面这样

```cpp
class handle {
protected:
    PyObject* m_ptr;
public:
    handle(PyObject* ptr) : m_ptr(ptr) {}

    friend bool operator==(const handle& lhs, const handle& rhs) {
        return PyObject_RichCompareBool(lhs.m_ptr, rhs.m_ptr, Py_EQ);
    }

    friend bool operator!=(const handle& lhs, const handle& rhs) {
        return PyObject_RichCompareBool(lhs.m_ptr, rhs.m_ptr, Py_NE);
    }

    // ...
};
```

大部分函数都是像上面这样简单包装一下，但有一些函数比较特殊。

## get/set 

根据 C++ 之父 Bjarne Stroustrup 在《The Design and Evolution of C++》中的说法，引入引用（左值）类型的部分原因是为了使得用户能够对返回值进行赋值，让`[]`这样的运算符的重载变的更加自然。例如：

```cpp
std::vector<int> v = {1, 2, 3};
int x = v[0]; // get
v[0] = 4;     // set
```

如果没有引用，就只能返回指针，那么上面的代码就得写成这样

```cpp
std::vector<int> v = {1, 2, 3};
int x = *v[0]; // get
*v[0] = 4;     // set
```

相比之下，使用引用是不是美观的多呢？这个问题在其它编程语言中也存在，但不是所有语言都采用这种解决办法。例如，Rust 选择自动解引用，编译器在合适的时机自动添加`*`来解引用，这样也就不需要多写上面那个`*`了。但是，这两种方法对 Python 来说都不行，因为 Python 中根本没有解引用这个说法，也不区分什么左值和右值。那怎么办呢？答案是区分`getter`和`setter`。

例如，如果要重载`[]`：

```python
class List:
    def __getitem__(self, key):
        print("__getitem__")
        return 1

    def __setitem__(self, key, value):
        print("__setitem__")

a = List()
x = a[0] # __getitem__
a[0] = 1 # __setitem__
```

Python 会检查语法结构，如果`[]` 出现在`=`的左边，就会调用`__setitem__`，否则就会调用`__getitem__`。实际上有挺多语言采用类似的设计的，例如 C# 的`this[]`运算符重载。

甚至连`.`运算符都可以重载，只需要重写`__getattr__`和`__setattr__`：

```python
class Point:
    def __getattr__(self, key):
        print(f"__getattr__")
        return 1

    def __setattr__(self, key, value):
        print(f"__setattr__")

p = Point()
x = p.x # __getattr__
p.x = 1 # __setattr__
```

pybind11 希望 handle 也能实现这样的效果，即在合适的时机调用`__getitem__`和`__setitem__`。例如：

```cpp
py::handle obj = py::list(1, 2, 3);
obj[0] = 4; // __setitem__
auto x = obj[0]; // __getitem__
x = py::int_(1);
```

对应的 Python 代码是

```python
obj = [1, 2, 3]
obj[0] = 4
x = obj[0]
x = 1
```

## accessor 

接下来就让我们重点讨论如何实现这样的效果。首先考虑`operator[]`的返回值，由于可能要调用`__setitem__`，所以这里我们返回一个代理对象。里面会把`key`存下来以备后续调用

```cpp
class accessor {
    handle m_obj;
    ssize_t m_key;
    handle m_value;
public:
    accessor(handle obj, ssize_t key) : m_obj(obj), m_key(key) {
        m_value = PyObject_GetItem(obj.ptr(), key);
    }
};
```

下面一个问题就是如何区分`obj[0] = 4`和`x = int_(1)`，使得前面一种情况调用`__setitem__`，后面一种情况就是简单的对`x`赋值。注意到上面两种情况的关键性区别，左值和右值

```cpp
obj[0] = 4; // assign to rvalue
auto x = obj[0]; 
x = 1; // assign to lvalue
```

如何让`operator=`根据操作数的值类别 (value category) 调用不同的函数呢？这就要用到一个比较少见的小技巧了，我们都知道可以在成员函数上加上`const`限定符，从而允许这个成员函数在 const 对象上调用。

```cpp
struct A {
    void foo() {}
    void bar() const {}
};

int main() {
    const A a;
    a.foo(); // error 
    a.bar(); // ok
}
```

除此之外，其实还可以加引用限定符`&`和`&&`，效果就是要求`expr.f()`的这个`expr`是左值还是右值。这样我们就可以根据左值和右值调用不同的函数了。

```cpp
struct A {
    void foo() & {}
    void bar() && {}
};

int main() {
    A a;
    a.foo(); // ok
    a.bar(); // error

    A().bar(); // ok
    A().foo(); // error
}
```

利用这个特性我们就能实现上面的效果了

```cpp
class accessor {
    handle m_obj;
    ssize_t m_key;
    handle m_value;
public:
    accessor(handle obj, ssize_t key) : m_obj(obj), m_key(key) {
        m_value = PyObject_GetItem(obj.ptr(), key);
    }

    // assign to rvalue
    void operator=(handle value) && {
        PyObject_SetItem(m_obj.ptr(), m_key, value.ptr());
    }

    // assign to lvalue
    void operator=(handle value) & {
        m_value = value;
    }
};
```

## lazy evaluation 

更进一步，我们希望这个代理对象仿佛就像一个`handle`一样，可以使用`handle`的所有方法。这很简单，直接继承`handle`就行了。

```cpp
class accessor : public handle {
    handle m_obj;
    ssize_t m_key;
public:
    accessor(handle obj, ssize_t key) : m_obj(obj), m_key(key) {
        m_ptr = PyObject_GetItem(obj.ptr(), key);
    }

    // assign to rvalue
    void operator=(handle value) && {
        PyObject_SetItem(m_ptr, m_key, value.ptr());
    }

    // assign to lvalue
    void operator=(handle value) & {
        m_ptr = value;
    }
};
```

到这似乎就结束了，但是注意到我们的`__getitem__`是在构造函数中调用的，也就是说即使后面没用到获取到的值，也会调用。感觉有进一步优化的空间，能不能通过一些手段把这个求值 lazy 化呢？只在需要调用`handle`里面这些函数的时候才去调用`__getitem__`呢？

目前这样直接继承`handle`肯定是不行的，不可能在每次成员函数调用之前插入一次判断，然后决定要不要调用`__getitem__`。可以让`handle`和`accessor`都继承一个基类，这个基类里面有一个有一个接口，用来实际获取要操作的指针

```cpp
class object_api{
public:
    virtual PyObject* get() = 0;

    bool operator==(const handle& rhs) {
        return PyObject_RichCompareBool(get(), rhs.ptr(), Py_EQ);
    }

    // ...
};
```

然后`handle`和`accessor`都继承这个基类，这时候`accessor`就可以在这里对`__getitem__`进行 lazy evaluation 了。

```cpp
class handle : public object_api {
    PyObject* get() override {
        return m_ptr;
    }
};

class accessor : public handle {
    PyObject* get() override {
        if (!m_ptr) {
            m_ptr = PyObject_GetItem(m_obj.ptr(), m_key);
        }
        return m_ptr;
    }
};
```

这样并不涉及到类型擦除，只是需要子类暴露出一个接口，所以理所应当的我们可以使用 [CRTP](https://en.cppreference.com/w/cpp/language/crtp) 来去虚化

```cpp
template <typename Derived>
class object_api {
public:
    PyObject* get() {
        return static_cast<Derived*>(this)->get();
    }

    bool operator==(const handle& rhs) {
        return PyObject_RichCompareBool(get(), rhs.ptr(), Py_EQ);
    }

    // ...
};

class handle : public object_api<handle> {
    PyObject* get() {
        return m_ptr;
    }
};

class accessor : public object_api<accessor> {
    PyObject* get() {
        if (!m_ptr) {
            m_ptr = PyObject_GetItem(m_obj.ptr(), m_key);
        }
        return m_ptr;
    }
};
```

这样我们就在不额外引入其它运行时开销的情况下把`__getitem__`的调用 lazy 化了。

## Conclusion 

我们常说 C++ 实在是太复杂了，各种眼花缭乱的特性太多了，不同特性之间还经常打架。那换一个角度来看待，特性多，意味着用户就有更多的选择，有更多的设计空间，就能组装出上述这样精彩的设计。我想很难有另外一门语言能实现这样的效果。或许这就是 C++ 的魅力所在吧。

文章到这里就结束了，感谢你的阅读，欢迎评论区讨论交流。