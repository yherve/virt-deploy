# -*- coding: utf-8 -*-
"""elementconf parser. Parses config files with a terraform/nginx style and
generates an ElementTree.

# e.g. libvirt network definition
# -------------------------------
network "mynet1name" {
    bridge.name="br0"
    forward.mode=nat
    forward.nat.port {start=1024 end=65535}
    ip {
       address=10.20.30.1
       netmask=255.255.255.0
       dhcp.range {start=10.20.30.40 end=10.20.30.254}
    }
}
"""
from __future__ import print_function

import re
import io
import sys
from copy import deepcopy
from lark import Lark, Transformer, v_args
from lark.exceptions import LarkError

try:
    from lxml import etree
except ImportError:
    import elementtree.ElementTree as etree

ElementConfError = LarkError

SIMPLE_VALUE = r'^[a-zA-Z0-9\/\:\.,_\-]+$'

TOKENS = r'''
    WS: /[ \t\f\r\n]/+
    COMMENT: /(#|\/\/)[^\n]*/
    MULTILINE_COMMENT:  "/*" /(.|\n|\r)+/ "*/"

    STRING_INNER: ("\\\""|/[^"]/)
    ESCAPED_STRING: "\""  STRING_INNER* "\""
    NAME: /[_a-zA-Z][a-zA-Z0-9\._\-]*/
    SIMPLE_VALUE:  /[a-zA-Z0-9\/\:\.,_\-]+/
    _SEP: ";"
    MULTILINE_STR:  "```" /(.|\n|\r)+/ "```"
'''

RULES=r"""
    start: element_children
    element: tag value_list ( "{" text element_children "}" | _SEP )
    element_children: (element|attribute)*
    attribute: key "=" value _SEP?

    tag: NAME
    key: NAME
    value: quoted_string|triple_quoted_string|SIMPLE_VALUE
    value_list: value*
    text: quoted_string?
    quoted_string: ESCAPED_STRING
    triple_quoted_string: MULTILINE_STR

    %ignore WS
    %ignore COMMENT
    %ignore MULTILINE_COMMENT
"""

GRAMMAR = TOKENS + RULES

DEFAULT_ROOT_NAME = "root"


def _get_sub_elem(parent, name_parts):
    """creates a hierarchy of sub-elements according to the list of 'name_parts.
    Only missing elements are created
    eg
    parent=<Element a><Element b>, name_parts="b.c.d"
    returns
    <Element a><Element b><Element c><Element d>
    """
    current_elt = parent
    for part in name_parts:
        new_current_elt = current_elt.find(part)
        if new_current_elt is None:
            new_current_elt = etree.SubElement(current_elt, part)
        current_elt = new_current_elt
    return current_elt


def _split_name(name):
    # return re.split("\.|/", name)
    return name.split(".")

def _append_elem(parent, elt):
    """append element to a parent.

    This may need to create intermediate nodes, eg

    parent=<Element a>, elt="<Element "b.c">
    returns
    <Element a><Element b><Element c>
    """
    name_parts = _split_name(elt.tag)
    current_elt = _get_sub_elem(parent, name_parts[0:-1])
    elt.tag = name_parts[-1]
    current_elt.append(elt)

def _set_attr(parent, key, value):
    """set an attribute to a parent.

    This may need to create intermediate nodes, eg:

    parent=<Element a>, key="b.c.k1", value="v1"
    returns
    <Element a><Element b><Element c, k1=v1>
    """
    name_parts = _split_name(key)
    current_elt = _get_sub_elem(parent, name_parts[0:-1])
    k = name_parts[-1]
    current_elt.attrib[k] = value.decode("utf-8")

def _append_list(parent, children):
    """append a list of Element to an Element.

    The list contains either tuples or elements. Tuples will become
    attributes.
    """
    if not children:
        return
    for elt in children:
        # pylint: disable=unidiomatic-typecheck
        if isinstance(elt, list):
            _append_list(parent, elt)
        elif type(elt) == type(parent):
            _append_elem(parent, elt)
        elif isinstance(elt, tuple):
            (key, value) = elt
            _set_attr(parent, key, value)



class ETreeTransformer(Transformer):
    """
    Transform a lark parsing tree into an ElementTree
    """
    _strtype = v_args(inline=True)(str)

    value_list = list
    attribute = tuple
    element_children = list

    text = _strtype
    key = _strtype
    value = _strtype
    tag = _strtype

    def __init__(self, root_name=DEFAULT_ROOT_NAME,
                 single_root_node=False, id_mapper=None):
        """
        - root_name: tag of the root xml element that is added implicitly.
                   Defaults to 'root'

        - single_root_node: if True, do not add a root xml element. In this case,
                          the conf must have a single root

        - id_mapper: a user function to set the value_list after the tag.
        e.g.

        Resource "testlab" "loadbalancer1" {
           ...
        }

        testlab and loadbalancer1 could be attributes of 'Resource'
        element or sub-element or whatever you want (see make_id_mapper_elt
        and make_id_mapper_attr for examples).

        """
        self.root_name = root_name
        self.single_root_node = single_root_node
        self.id_mapper = id_mapper


    # pylint: disable=no-self-use
    @v_args(inline=True)
    def triple_quoted_string(self, arg):
        "remove quote and replace escapes"
        res = arg[3:-3]
        return res.encode("utf-8")


    # pylint: disable=no-self-use
    @v_args(inline=True)
    def quoted_string(self, arg):
        "remove quote and replace escapes"
        res = arg[1:-1]
        replace_list = [
            ("\\\"", "\""),
            ("\\\\", "\\"),
            ("\\/", "/"),
            ("\\b", "\b"),
            ("\\n", "\n"),
            ("\\r", "\r"),
            ("\\t", "\t")
        ]
        for replace_tuple in replace_list:
            res = res.replace(*replace_tuple)
        return res.encode("utf-8")

    @v_args(inline=True)
    def start(self, children=None):
        "match start of the grammar"
        if self.single_root_node:
            if len(children) != 1:
                raise Exception(
                    "Error: the document does not contain a single "\
                    "top level element")
            return children[0]

        if not self.root_name:
            return children

        elt = etree.Element(self.root_name)
        _append_list(elt, children)
        return elt

    @v_args(inline=True)
    def element(self, tag, value_list=None, text=None, children=None):
        "create ElementTree node"
        elt = etree.Element(tag)
        if text:
            elt.text = text.decode("utf-8")

        if value_list and children is None:
            elt_lst = []
            if text:
                elt_lst.append(elt)

            for value in value_list:
                xelt = etree.Element(tag)
                xelt.text = value.decode("utf-8")
                elt_lst.append(xelt)
            return elt_lst

        _append_list(elt, children)

        if value_list and children is not None and self.id_mapper:
            self.id_mapper(elt, value_list)

        return elt


class ElementConf(object):
    """class similar to ElementTree. Acts as a wrapper of root Element"""

    def __init__(self, root=None):
        """
        root is an instance of "Element"
        """
        self.root = root

    def getroot(self):
        "get root element"
        return self.root

    def find(self, match):
        "Same as Element.find(), starting at the root of the tree."
        if self.root is not None:
            return self.root.find(match)
        return None

    def findall(self, match):
        "Same as Element.findall(), starting at the root of the tree."
        if self.root is not None:
            return self.root.findall(match)
        return None

    def iter(self, tag=None):
        "Creates and returns a tree iterator for the root element"
        if self.root is not None:
            return self.root.iter(tag)
        return None

    def iterfind(self, match):
        "Finds all matching subelements, by tag name or path"
        if self.root is not None:
            return self.root.iterfind(match)
        return None

    def parse(self, source, **args):
        """load a config from a string"""
        transformer = ETreeTransformer(**args)
        parser = Lark(GRAMMAR, parser='lalr', transformer=transformer)
        self.root = parser.parse(source)

    def toxml(self, pretty_print=False):
        "return a xml representation of elementconf as a string"
        if self.root is not None:
            res = etree.tostring(self.root, pretty_print=pretty_print)
            return res
        return None

def loads(strng, root_name=DEFAULT_ROOT_NAME,
          single_root_node=False, id_mapper=None):
    """load a config from a string.

    Args:
        strng: the string containing the config file
        root_name: the tag for the top-level node that is added implicitly
        single_root_node: if true, no implicit top-level
        id_mapper: a function to set the 'value_list' of an element

        id_mapper(Element, list) -> None

    see below examples of id_mapper

    Returns:
       instance of ElementConf
    Raises:
       ElementConfError
    """
    el_conf = ElementConf()
    el_conf.parse(strng, root_name=root_name,
                  single_root_node=single_root_node,
                  id_mapper=id_mapper)
    return el_conf

def load(fname, root_name=DEFAULT_ROOT_NAME,
         single_root_node=False, id_mapper=None):
    """load a config from a file. see loads for argument description"""
    with io.open(fname, encoding="utf-8") as config_file:
        content = config_file.read()
        return loads(content, root_name, single_root_node, id_mapper)


SIMPLE_VALUE_RE=re.compile(SIMPLE_VALUE)
def _maybe_quote(value):
    # todo proper quoting \n \t...
    # no_quote_needed = (SIMPLE_VALUE_RE.match(value) and len(value)<30)
    no_quote_needed = (SIMPLE_VALUE_RE.match(value))
    v = value if no_quote_needed else '"' + value + '"'
    return v


def elt_merge(change, base):
    """
    merge 'change' element into 'base'

    :param change: instance of Element
    :param base: instance of Element

    :returns: nothing, 'base' object changed directly
    """
    for k,v in change.attrib.items():
        base.set(k, v)
    for child_change in change:
        child_base = base.find(child_change.tag)
        if child_base is not None:
            elt_merge(child_change, child_base)
        else:
            # adding new node. just need to deep copy
            base.append(deepcopy(child_change))



def el_to_struct(elt, print_root=True):
    children = []

    attrs = dict(elt.attrib)
    # if len(attrs):
    #     children.append(attrs)
    # else:
    #     children.append({})

    if elt.text:
        attrs["_TEXT"] = elt.text

    children.append(attrs)

    for ch in elt:
        ch_struct = el_to_struct(ch)
        children.append(ch_struct)

    if len(children) == 1 and children[0] is None:
        children={}

    if print_root:
        res = {elt.tag:children}
    else:
        res = children[1:]
    return res



def el_to_conf(elt, indent=0, indent_chars=" "*4, print_root=True):
    """dump Element instance to conf format

    :param elt: instance of Element
    :returns: string containing conf representation of the element
    """
    indent_str = indent_chars*indent
    res = ""

    if print_root:
        res = '{}{}'.format(indent_str, elt.tag)

        if len(elt) == 0 and len(elt.attrib) == 0:
            if elt.text:
                res += " " + _maybe_quote(elt.text)
            res += ";\n"
            return res

        res += " {\n"
        indent_str += indent_chars
        indent+=1
    if elt.text:
        # todo proper quoting
        res += indent_str + '"' + elt.text + '"\n'

    mx=0
    for value in elt.keys():
        if len(value)>mx:
            mx = len(value)

    for name, value in elt.items():
        v = _maybe_quote(value)
        fmt = '{}{:'+str(mx)+'} = {}\n'
        res +=fmt.format(indent_str, name.encode('utf8'), v.encode('utf8'))

    for child in elt:
        if not print_root:
            res +='\n'
        res += el_to_conf(child, indent)

    if print_root:
        indent-=1
        indent_str = indent_chars*indent
        res += indent_str + '}\n'
    return res


def make_id_mapper_attr(attr_name):
    """returns a function to map id to attribute.

    Example with make_id_mapper_attr("myname"):

    user "toto" {}
      becomes
    <user myname="toto"/>
    """
    return lambda elt, idlist: elt.set(attr_name, idlist[-1])

def make_id_mapper_elt(elt_name):
    """returns a function to map id to sub-element.

    Example with make_id_mapper_elt("myname"):

    user "toto" {}
      becomes
    <user>
       <myname>toto</myname>
    </user>
    """
    def _id_mapper(elt_name, elt, idlist):
        id_elt = etree.Element(elt_name)
        id_elt.text = idlist[-1]
        elt.insert(0, id_elt)
    return lambda elt, idlist: _id_mapper(elt_name, elt, idlist)


def test_convert():
    """takes an element.conf file and dumps corresponding xml
    """
    if len(sys.argv) < 2:
        print("usage: {} <filename>".format(sys.argv[0]))
        sys.exit(1)
    try:
        result = load(sys.argv[1])
        print(result.toxml(pretty_print=True))
    except ElementConfError as exc:
        print("Got syntax error: {}".format(exc))

if __name__ == '__main__':
    test_convert()
