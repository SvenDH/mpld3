import abc
import uuid
import warnings

import numpy as np

from ._utils import get_text_coordinates, color_to_hex, get_dasharray, get_d3_shape_for_marker



class D3Base(object):
    """Abstract Base Class for D3js objects"""
    __metaclass__ = abc.ABCMeta

    def _initialize(self, parent=None, **kwds):
        self.parent = parent
        for key, val in kwds.items():
            setattr(self, key, val)

    @property
    def figid(self):
        if hasattr(self, '_figid'):
            return self._figid
        elif self.parent is not None and self.parent is not self:
            return self.parent.figid
        else:
            raise AttributeError("no attribute figid")

    @property
    def axid(self):
        if hasattr(self, '_axid'):
            return self._axid
        elif self.parent is not None and self.parent is not self:
            return self.parent.axid
        else:
            raise AttributeError("no attribute axid")

    @abc.abstractmethod
    def html(self):
        raise NotImplementedError()

    def style(self):
        return ''

    def zoom(self):
        return ''

    def __str__(self):
        return self.html()
        

class D3Figure(D3Base):
    """Class for representing a matplotlib Figure in D3js"""
    D3_IMPORT = """
    <script type="text/javascript" src="http://d3js.org/d3.v3.min.js"></script>
    """

    STYLE = """
    <style>
    {styles}
    </style>
    """

    FIGURE_TEMPLATE = """
    <div id='figure{figid}'></div>

    <script type="text/javascript">
    func{figid} = function(figure){{

    var figwidth = {figwidth} * {dpi};
    var figheight = {figheight} * {dpi};

    var canvas = figure.append('svg:svg')
                   .attr('width', figwidth)
                   .attr('height', figheight)
                   .attr('class', 'canvas')

    {axes}

    }}

    // set a timeout of 0 to allow d3.js to load
    setTimeout(function(){{ func{figid}(d3.select('#figure{figid}')) }}, 0)
    </script>
    """
    @staticmethod
    def generate_figid():
        return str(uuid.uuid4()).replace('-', '')

    def __init__(self, fig):
        # use time() to make sure multiple versions of this figure
        # don't cross-talk if used on the same page.
        self._initialize(parent=None, fig=fig)
        self._figid = self.generate_figid()
        self.axes = [D3Axes(self, ax, i + 1)
                     for i, ax in enumerate(fig.axes)]

    def style(self):
        return self.STYLE.format(styles='\n'.join([ax.style()
                                                   for ax in self.axes]))

    def html(self):
        axes = '\n'.join(ax.html() for ax in self.axes)
        fig = self.FIGURE_TEMPLATE.format(figid=self.figid,
                                          figwidth=self.fig.get_figwidth(),
                                          figheight=self.fig.get_figheight(),
                                          dpi=self.fig.dpi,
                                          axes=axes)
        return self.D3_IMPORT + self.style() + fig


class D3Axes(D3Base):
    """Class for representing a matplotlib Axes in D3js"""
    STYLE = """
    div#figure{figid}
    .axes{axid}.axis line, .axes{axid}.axis path {{
        shape-rendering: crispEdges;
        stroke: black;
        fill: none;
    }}

    div#figure{figid}
    .axes{axid}.axis text {{
        font-family: sans-serif;
        font-size: {fontsize}px;
        fill: black;
        stroke: none;
    }}
    """

    AXES_TEMPLATE = """
    // store the width and height of the axes
    var width_{axid} = {bbox[2]} * figwidth;
    var height_{axid} = {bbox[3]} * figheight

    // create the x and y axis
    var x_{axid} = d3.scale.linear()
                       .domain([{xlim[0]}, {xlim[1]}])
                       .range([0, width_{axid}]);

    var y_{axid} = d3.scale.linear()
                       .domain([{ylim[0]}, {ylim[1]}])
                       .range([height_{axid}, 0]);

    // zoom object for the axes
    var zoom{axid} = d3.behavior.zoom()
                    .x(x_{axid})
                    .y(y_{axid})
                    .on("zoom", zoomed{axid});

    // create the axes itself
    var baseaxes_{axid} = canvas.append('g')
            .attr('transform', 'translate(' + ({bbox[0]} * figwidth) + ',' +
                              ((1 - {bbox[1]} - {bbox[3]}) * figheight) + ')')
            .attr('width', width_{axid})
            .attr('height', height_{axid})
            .attr('class', 'main')
            .call(zoom{axid});

    // create the axes background
    baseaxes_{axid}.append("svg:rect")
                      .attr("width", width_{axid})
                      .attr("height", height_{axid})
                      .attr("class", "bg{axid}")
                      .attr("fill", "{axesbg}");

    // axis factory functions: used for grid lines & axes
    var create_xAxis_{axid} = function(){{
       return d3.svg.axis()
            .scale(x_{axid})
            .orient('bottom');
    }}

    var create_yAxis_{axid} = function(){{
       return d3.svg.axis()
            .scale(y_{axid})
            .orient('left');
    }}

    // draw the x axis
    var xAxis_{axid} = create_xAxis_{axid}();

    baseaxes_{axid}.append('g')
            .attr('transform', 'translate(0,' + (height_{axid}) + ')')
            .attr('class', 'axes{axid} x axis')
            .call(xAxis_{axid});

    // draw the y axis
    var yAxis_{axid} = create_yAxis_{axid}();

    baseaxes_{axid}.append('g')
            .attr('transform', 'translate(0,0)')
            .attr('class', 'axes{axid} y axis')
            .call(yAxis_{axid});

    // create the clip boundary
    var clip_{axid} = baseaxes_{axid}.append("svg:clipPath")
                             .attr("id", "clip{axid}")
                             .append("svg:rect")
                             .attr("x", 0)
                             .attr("y", 0)
                             .attr("width", width_{axid})
                             .attr("height", height_{axid});
 
    // axes_{axid} is the axes on which to draw plot components: they'll
    // be clipped when zooming or scrolling moves them out of the plot.
    var axes_{axid} = baseaxes_{axid}.append('g')
            .attr("clip-path", "url(#clip{axid})");
    
    {elements}

    function zoomed{axid}() {{
        //console.log(d3.event.translate);
        //console.log(d3.event.scale);
        baseaxes_{axid}.select(".x.axis").call(xAxis_{axid});
        baseaxes_{axid}.select(".y.axis").call(yAxis_{axid});

        {element_zooms}
    }}
    """
    def __init__(self, parent, ax, i):
        self._initialize(parent=parent, ax=ax)
        self._axid = self.figid + str(i)
        self.lines = [D3Line2D(self, line, i + 1)
                      for i, line in enumerate(ax.lines)]
        self.texts = [D3Text(self, ax, text) for text in
                      ax.texts + [ax.xaxis.label, ax.yaxis.label, ax.title]]
        self.grids = [D3Grid(self, ax)]

        # Some warnings for pieces of matplotlib which are not yet implemented
        for attr in ['images', 'collections', 'containers',
                     'artists', 'patches', 'tables']:
            if len(getattr(ax, attr)) > 0:
                warnings.warn("{0} not implemented.  "
                              "Elements will be ignored".format(attr))

        if ax.legend_ is not None:
            warnings.warn("legend is not implemented: it will be ignored")

    def style(self):
        ticks = self.ax.xaxis.get_ticklabels() + self.ax.yaxis.get_ticklabels()
        if len(ticks) == 0:
            fontsize_x = 11
        else:
            fontsize_x = ticks[0].properties()['size']
        return '\n'.join([self.STYLE.format(axid=self.axid,
                                            figid=self.figid,
                                            fontsize=fontsize_x)] + 
                         [g.style() for g in self.grids] +
                         [l.style() for l in self.lines] +
                         [t.style() for t in self.texts])

    def html(self):
        elements = '\n'.join([elem.html() for elem in
                              (self.grids + self.lines + self.texts)])
        zooms = '\n'.join(elem.zoom() for elem in
                          (self.grids + self.lines + self.texts))

        return self.AXES_TEMPLATE.format(id=id(self.ax),
                                         axid=self.axid,
                                         xlim=self.ax.get_xlim(),
                                         ylim=self.ax.get_ylim(),
                                         bbox=self.ax.get_position().bounds,
                                         axesbg='#FCFCFC',
                                         elements=elements,
                                         element_zooms=zooms)


class D3Grid(D3Base):
    """Class for representing a matplotlib Axes grid in D3js"""
    STYLE = """
    div#figure{figid}
    .grid .tick {{
      stroke: {color};
      stroke-dasharray: {dasharray};
      stroke-opacity: {alpha};
    }}
    
    div#figure{figid}
    .grid path {{
      stroke-width: 0;
    }}
    """

    XGRID_TEMPLATE = """
    // draw x grid lines: we use a second x-axis with long ticks
    axes_{axid}.append("g")
         .attr("class", "axes{axid} x grid")
         .attr("transform", "translate(0," + (height_{axid}) + ")")
         .call(create_xAxis_{axid}()
                       .tickSize(-(height_{axid}), 0, 0)
                       .tickFormat(""));
    """

    YGRID_TEMPLATE = """
    // draw y grid lines: we use a second y-axis with long ticks
    axes_{axid}.append("g")
         .attr("class", "axes{axid} y grid")
         .call(create_yAxis_{axid}()
                       .tickSize(-(width_{axid}), 0, 0)
                       .tickFormat(""));
    """

    XZOOM = """
        axes_{axid}.select(".x.grid")
            .call(create_xAxis_{axid}()
            .tickSize(-(height_{axid}), 0, 0)
            .tickFormat(""));
    """

    YZOOM = """
        axes_{axid}.select(".y.grid")
            .call(create_yAxis_{axid}()
            .tickSize(-(width_{axid}), 0, 0)
            .tickFormat(""));
    """
    def __init__(self, parent, ax):
        self._initialize(parent=parent, ax=ax)

    def zoom(self):
        ret = ""
        bbox = self.ax.get_position().bounds
        if self.ax.xaxis._gridOnMajor:
            ret += self.XZOOM.format(axid=self.axid,
                                     bbox=bbox)
        if self.ax.yaxis._gridOnMajor:
            ret += self.YZOOM.format(axid=self.axid,
                                     bbox=bbox)
        return ret

    def html(self):
        ret = ""
        bbox = self.ax.get_position().bounds
        if self.ax.xaxis._gridOnMajor:
            ret += self.XGRID_TEMPLATE.format(axid=self.axid,
                                              bbox=bbox)
        if self.ax.yaxis._gridOnMajor:
            ret += self.YGRID_TEMPLATE.format(axid=self.axid,
                                              bbox=bbox)
        return ret

    def style(self):
        gridlines = (self.ax.xaxis.get_gridlines() +
                     self.ax.yaxis.get_gridlines())
        color = color_to_hex(gridlines[0].get_color())
        alpha = gridlines[0].get_alpha()
        dasharray = get_dasharray(gridlines[0])
        return self.STYLE.format(color=color,
                                 alpha=alpha,
                                 figid=self.figid,
                                 dasharray=dasharray)


class D3Line2D(D3Base):
    """Class for representing a 2D matplotlib line in D3js"""
    DATA_TEMPLATE = """
    var data_{lineid} = {data}
    """

    STYLE = """
    div#figure{figid}
    path.line{lineid} {{
        stroke: {linecolor};
        stroke-width: {linewidth};
        stroke-dasharray: {dasharray};
        fill: none;
        stroke-opacity: {alpha};
    }}

    div#figure{figid}
    path.points{lineid} {{
        stroke-width: {markeredgewidth};
        stroke: {markeredgecolor};
        fill: {markercolor};
        fill-opacity: {alpha};
        stroke-opacity: {alpha};
    }}
    """

    LINE_ZOOM = """
        axes_{axid}.select(".line{lineid}")
                       .attr("d", line_{lineid}(data_{lineid}));
    """

    POINTS_ZOOM = """
        axes_{axid}.selectAll(".points{lineid}")
              .attr("transform", function(d) {{ return "translate(" + x_{axid}(d[0]) + "," + y_{axid}(d[1]) + ")"; }});
    """

    LINE_TEMPLATE = """
    var line_{lineid} = d3.svg.line()
         .x(function(d) {{return x_{axid}(d[0]);}})
         .y(function(d) {{return y_{axid}(d[1]);}})
         .interpolate("linear");

    axes_{axid}.append("svg:path")
                   .attr("d", line_{lineid}(data_{lineid}))
                   .attr('class', 'line{lineid}');
    """

    POINTS_TEMPLATE = """
    var g_{lineid} = axes_{axid}.append("svg:g");

    g_{lineid}.selectAll("scatter-dots-{lineid}")
          .data(data_{lineid})
          .enter().append("svg:path")
              .attr('class', 'points{lineid}')
              .attr("d", d3.svg.symbol().type("{markershape}").size({markersize}))
              .attr("transform", function(d) {{ return "translate(" + x_{axid}(d[0]) + "," + y_{axid}(d[1]) + ")"; }});

    """
    def __init__(self, parent, line, i=''):
        self._initialize(parent=parent, line=line)
        self.lineid = "{0}{1}".format(self.axid, i)

    def has_line(self):
        return self.line.get_linestyle() not in ['', ' ', 'None',
                                                 'none', None]

    def has_points(self):
        return self.line.get_marker() not in ['', ' ', 'None', 'none', None]

    def zoom(self):
        ret = ""
        if self.has_points():
            ret += self.POINTS_ZOOM.format(lineid=self.lineid,
                                           axid=self.axid)
        if self.has_line():
            ret += self.LINE_ZOOM.format(lineid=self.lineid,
                                         axid=self.axid)
        return ret

    def style(self):
        alpha = self.line.get_alpha()
        if alpha is None:
            alpha = 1
        lc = color_to_hex(self.line.get_color())
        lw = self.line.get_linewidth()
        ms = 10. * self.line.get_markersize()
        mc = color_to_hex(self.line.get_markerfacecolor())
        mec = color_to_hex(self.line.get_markeredgecolor())
        mew = self.line.get_markeredgewidth()
        dasharray = get_dasharray(self.line)

        return self.STYLE.format(figid=self.figid,
                                 lineid=self.lineid,
                                 linecolor=lc,
                                 linewidth=lw,
                                 markersize=ms,
                                 markeredgewidth=mew,
                                 markeredgecolor=mec,
                                 markercolor=mc,
                                 dasharray=dasharray,
                                 alpha=alpha)
        
    def html(self):
        data = self.line.get_xydata().tolist()
        alpha = self.line.get_alpha()
        if alpha is None:
            alpha = 1
        result = self.DATA_TEMPLATE.format(lineid=self.lineid, data=data)

        if self.has_points():
            # TODO: use actual marker, not simply circles
            marker = self.line.get_marker()
            msh = get_d3_shape_for_marker(marker)
            ms = 10. * self.line.get_markersize()
            result += self.POINTS_TEMPLATE.format(lineid=self.lineid,
                                                  axid=self.axid,
                                                  markersize=ms,
                                                  markershape=msh,
                                                  data=data)
        if self.has_line():
            # TODO: use actual line style
            style = self.line.get_linestyle()
            result += self.LINE_TEMPLATE.format(lineid=self.lineid,
                                                axid=self.axid,
                                                data=data)
        return result


class D3Text(D3Base):
    """Class for representing matplotlib text in D3js"""
    TEXT_TEMPLATE = """
    canvas.append("text")
        .text("{text}")
        .attr("class", "axes-text")
        .attr("x", {x})
        .attr("y", figheight - {y})
        .attr("font-size", "{fontsize}px")
        .attr("fill", "{color}")
        .attr("transform", "rotate({rotation},{x}," + (figheight - {y}) + ")")
        .attr("style", "text-anchor: {anchor};")
    """
    def __init__(self, parent, ax, text):
        self._initialize(parent=parent, ax=ax, text=text)
    
    def html(self):
        if not self.text.get_text():
            return ''
        
        if self.text.get_transform() is self.ax.transData:
            # TODO: anchor this text to the axes, rather than to the figure.
            pass

        x, y = get_text_coordinates(self.text)
        color =  color_to_hex(self.text.get_color())
        fontsize = self.text.get_size()

        # TODO: fix vertical/horizontal spacing and anchor point
        # hack for y-label alignment
        if self.text is self.ax.yaxis.label:
            x += fontsize
            
        return self.TEXT_TEMPLATE.format(text=self.text.get_text(),
                                         x=x, y=y,
                                         fontsize=fontsize,
                                         color=color,
                                         rotation=-self.text.get_rotation(),
                                         anchor="middle")
