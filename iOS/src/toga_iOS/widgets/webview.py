import json
import re
import time

from rubicon.objc import NSInteger, ObjCBlock, objc_method, objc_property, py_from_ns
from rubicon.objc.runtime import c_void_p, objc_id
from travertino.size import at_least

from toga.widgets.webview import JavaScriptResult
from toga_iOS.libs import (
    NSURL,
    NSURLRequest,
    UIScreen,
    UIView,
    WKWebView,
    WKWebViewConfiguration,
    CGRect,
    UIColor,
)
from toga_iOS.app import App
from toga_iOS.widgets.base import Widget


def js_completion_handler(future, on_result=None):
    def _completion_handler(res: objc_id, error: objc_id) -> None:
        if error:
            error = py_from_ns(error)
            exc = RuntimeError(str(error))
            future.set_exception(exc)
            if on_result:
                on_result(None, exception=exc)
        else:
            result = py_from_ns(res)
            future.set_result(result)
            if on_result:
                on_result(result)

    return _completion_handler


def parse_color_rule(color_rule_str, default_color):
    color_matches = re.match(r"rgb\((\d+),\s*(\d+),\s*(\d+)\)", color_rule_str)
    if color_matches:
        color = (int(color_matches[1]), int(color_matches[2]), int(color_matches[3]), 255)
    else:
        color_matches = re.match(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)", color_rule_str)
        if color_matches:
            color = (int(color_matches[1]), int(color_matches[2]), int(color_matches[3]), int(color_matches[4]))
        else:
            color = default_color
    # unset backgrounds are (0, 0, 0, 0)
    if color == (0, 0, 0, 0):
        color = default_color
    return color


class TogaWebView(WKWebView):
    interface = objc_property(object, weak=True)
    impl = objc_property(object, weak=True)

    @objc_method
    def userContentController_didReceiveScriptMessage_(self, userContentController, message) -> None:
        if App.app.interface.first_load:
            App.app.interface.finish_launch()
        colors = json.loads(str(message.body))
        top_colors = parse_color_rule(colors["top_background"], self.interface.bg_color)
        topColor = UIColor.colorWithRed(
            top_colors[0] / 255.0, green=top_colors[1] / 255.0, blue=top_colors[2] / 255.0, alpha=top_colors[3] / 255.0
        )
        self.impl.topBackgroundView.backgroundColor = topColor
        self.superview().insertSubview(self.impl.topBackgroundView, belowSubview=self)

        bottom_colors = parse_color_rule(colors["bottom_background"], self.interface.bg_color)
        bottomColor = UIColor.colorWithRed(
            bottom_colors[0] / 255.0,
            green=bottom_colors[1] / 255.0,
            blue=bottom_colors[2] / 255.0,
            alpha=bottom_colors[3] / 255.0,
        )
        self.impl.bottomBackgroundView.backgroundColor = bottomColor
        self.superview().insertSubview(self.impl.bottomBackgroundView, belowSubview=self)
        
    # @objc_method
    # def webView_didStartProvisionalNavigation_(self, webView, navigation) -> None:
    #     self.impl.url = str(self.URL)
        
    # @objc_method
    # def webView_didReceiveServerRedirectForProvisionalNavigation_(self, webView, navigation) -> None:
    #     self.impl.url = str(self.URL)


    @objc_method
    def webView_didFinishNavigation_(self, webview, navigation) -> None:
        self.interface.on_webview_load(self.interface)
        if self.impl.loaded_future:
            self.impl.loaded_future.set_result(None)
            self.impl.loaded_future = None

    @objc_method
    def webView_didFailProvisionalNavigation_withError_(self, webview, navigation, error) -> None:
        self.impl.web_view_error_flag = True

    @objc_method
    def webView_requestMediaCapturePermissionForOrigin_initiatedByFrame_type_decisionHandler_(
        self, webview, origin, frame, captureType: NSInteger, decisionHandler
    ) -> None:
        obj_decisionHandler = ObjCBlock(decisionHandler, c_void_p, NSInteger)
        if origin.host == "127.0.0.1":
            obj_decisionHandler(1)
        else:
            obj_decisionHandler(0)


class WebView(Widget):
    def create(self):
        conf = WKWebViewConfiguration.alloc().init()
        conf.allowsInlineMediaPlayback = True
        conf.suppressesIncrementalRendering = True
        conf.mediaTypesRequiringUserActionForPlayback = 0
        self.native = TogaWebView.alloc().initWithFrame(UIScreen.mainScreen.bounds, configuration=conf)
        self.native.interface = self.interface
        self.native.impl = self

        # Enable the content inspector. This was added in iOS 16.4.
        # It is a no-op on earlier versions.
        self.native.inspectable = True
        self.native.navigationDelegate = self.native

        self.native.UIDelegate = self.native

        self.native.allowsLinkPreview = False
        self.native.scrollView.setContentInsetAdjustmentBehavior(2)
        self.native.scrollView.backgroundColor = UIColor.clearColor
        self.native.configuration.userContentController.addScriptMessageHandler(self.native, name="finished_loading")

        screenWidth = min(UIScreen.mainScreen.bounds.size.height, UIScreen.mainScreen.bounds.size.width)
        screenHeight = max(UIScreen.mainScreen.bounds.size.height, UIScreen.mainScreen.bounds.size.width)
        topRect = CGRect((0, 0), (screenHeight, 0.69 * screenWidth))
        self.topBackgroundView = UIView.alloc().initWithFrame(topRect)
        bottomRect = CGRect((0, 0.69 * screenWidth), (screenHeight, screenHeight - 0.69 * screenWidth))
        self.bottomBackgroundView = UIView.alloc().initWithFrame(bottomRect)

        self.loaded_future = None

        self.web_view_error_flag = False

        # Add the layout constraints
        self.add_constraints()

    def get_url(self):
        url = str(self.native.URL)
        return None if url == "about:blank" else url

    def set_url(self, value, future=None):
        if value:
            request = NSURLRequest.requestWithURL(NSURL.URLWithString(value))
        else:
            request = NSURLRequest.requestWithURL(NSURL.URLWithString("about:blank"))

        self.loaded_future = future
        self.native.loadRequest(request)

    def set_content(self, root_url, content):
        self.native.loadHTMLString(content, baseURL=NSURL.URLWithString(root_url))

    def get_user_agent(self):
        return str(self.native.valueForKey("userAgent"))

    def set_user_agent(self, value):
        self.native.customUserAgent = value

    def evaluate_javascript(self, javascript, on_result=None):
        result = JavaScriptResult()
        self.native.evaluateJavaScript(
            javascript,
            completionHandler=js_completion_handler(
                future=result.future,
                on_result=on_result,
            ),
        )

        return result

    def rehint(self):
        self.interface.intrinsic.width = at_least(self.interface._MIN_WIDTH)
        self.interface.intrinsic.height = at_least(self.interface._MIN_HEIGHT)
